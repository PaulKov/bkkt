from __future__ import annotations

from pathlib import Path

from ...app.context import CliContext
from ...cli_helpers.clusters_arg import parse_clusters_selection
from ...cli_helpers.default_scope_ux import (
    confirm_broad_scope,
    effective_value,
    log_effective_values,
)
from ...exceptions import ConfigError
from ...logging_utils import get_logger
from ...output import (
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
)
from ...repo import ConnectorRepo
from ...routing import ClusterRouter
from ...validation import ConfigTestRunner

from ...rendering.factory import build_renderer
from ...rendering.runtime_vars import load_runtime_vars_with_sources

from .collector import collect_drift
from .markdown import build_drift_markdown
from .options import options_from_args
from .selection import select_manifest_paths


class DriftService:
    """Service that builds a drift report between repo manifests and live Kafka Connect."""

    def __init__(self, *, ctx: CliContext, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)

    def run(self, args) -> int:
        repo_root = self.ctx.repo_root
        settings = self.ctx.settings

        env = self.ctx.env(args.env)
        cluster_name = getattr(args, "cluster", None)
        selected_clusters = parse_clusters_selection(
            getattr(args, "clusters", None),
            available=settings.cluster_groups.keys(),
            allow_all_keyword=True,
        )
        if cluster_name and selected_clusters is not None:
            raise ConfigError(
                "Нельзя использовать одновременно --cluster (single target) и --clusters (multi-cluster)"
            )
        log_effective_values(
            self.log,
            command="drift",
            values=(
                effective_value(args, "env", env.value),
                effective_value(args, "cluster", cluster_name or "-"),
                effective_value(
                    args,
                    "clusters",
                    ",".join(selected_clusters) if selected_clusters else "-",
                ),
                effective_value(args, "output", resolve_output_format(args).value),
            ),
        )
        if selected_clusters is not None:
            if not confirm_broad_scope(
                args,
                prompt=(
                    "Продолжить multi-cluster drift "
                    f"для env={env.value} clusters={','.join(selected_clusters)}?"
                ),
                logger=self.log,
            ):
                return 1
            return self._run_multi_cluster(
                args=args,
                env=env,
                selected_clusters=selected_clusters,
            )

        target = self.ctx.connect_target(env, cluster_name)
        self.ctx.print_cluster_banner(target)

        config_test_runner = ConfigTestRunner.from_settings(
            repo_root=repo_root, config_tests=settings.config_tests
        )

        repo = ConnectorRepo(settings.repo, fs=self.ctx.fs)
        renderer = build_renderer(
            settings,
            fs=self.ctx.fs,
            routing_cli_cluster=cluster_name,
        )
        runtime_vars, _runtime_sources = load_runtime_vars_with_sources(args, repo_root)
        connect = target.client

        env_files = select_manifest_paths(ctx=self.ctx, args=args, env=env, repo=repo)
        if not env_files:
            self.log.info("No connector manifests selected for drift")
            return 0

        options = options_from_args(args)

        collected = collect_drift(
            policy_env=env,
            env_files=env_files,
            repo_root=repo_root,
            repo=repo,
            renderer=renderer,
            runtime_vars=runtime_vars,
            connect=connect,
            config_test_runner=config_test_runner,
            strict_naming=options.strict_naming,
            policies=options.policies,
            naming=settings.naming,
            options=options,
            cluster_group=target.cluster.name,
            prune_config_keys=target.cluster.render_prune_config_keys,
            logger=self.log,
        )

        md = build_drift_markdown(
            env=env,
            manifests_checked=collected.manifests_checked,
            ok_count=collected.ok_count,
            disabled_skipped=collected.disabled_skipped,
            drift_count=collected.drift_count,
            missing_count=collected.missing_count,
            group_stats_dt=collected.group_stats_dt,
            group_stats_dts=collected.group_stats_dts,
            drift_key_counter=collected.drift_key_counter,
            drift_override_source_counter=collected.drift_override_source_counter,
            detailed=collected.detailed,
            include_diffs=options.include_diffs,
            max_lines=options.max_lines,
            top_n=options.top_n,
        )

        out_path = getattr(args, "output_file", None)
        if out_path:
            self.ctx.fs.write_text(Path(out_path), md, encoding="utf-8")

        fmt = resolve_output_format(args)
        if is_machine_output(fmt):
            payload = {
                "command": "drift",
                "comparison_mode": "post_prune",
                "env": env.value,
                "cluster": {
                    "group": target.cluster.name,
                    "env": target.cluster.env.value,
                    "urls": list(target.cluster.urls),
                },
                "counts": {
                    "manifests_checked": collected.manifests_checked,
                    "ok": collected.ok_count,
                    "drift": collected.drift_count,
                    "missing": collected.missing_count,
                },
                "lifecycle": {
                    "disabled_skipped": collected.disabled_skipped,
                },
                "group_stats": {
                    "dt": collected.group_stats_dt,
                    "dts": collected.group_stats_dts,
                },
                "top": {
                    "drift_keys": [
                        {"key": k, "count": c}
                        for (k, c) in collected.drift_key_counter.most_common(
                            options.top_n
                        )
                    ],
                    "override_sources": [
                        {"source": k, "count": c}
                        for (
                            k,
                            c,
                        ) in collected.drift_override_source_counter.most_common(
                            options.top_n
                        )
                    ],
                },
                "detailed": collected.detailed,
                "options": {
                    "include_diffs": options.include_diffs,
                    "max_lines": options.max_lines,
                    "top": options.top_n,
                    "fail_on_drift": options.fail_on_drift,
                },
            }
            write_payload(payload, fmt=fmt)

            # Markdown оставляем в логах (stderr), чтобы stdout был машинно‑читаемым.
            self.log.info("%s", md)
        else:
            write_text(md)

        if options.fail_on_drift and (collected.drift_count or collected.missing_count):
            return 2
        return 0

    def _run_multi_cluster(self, *, args, env, selected_clusters: list[str]) -> int:
        repo_root = self.ctx.repo_root
        settings = self.ctx.settings

        config_test_runner = ConfigTestRunner.from_settings(
            repo_root=repo_root, config_tests=settings.config_tests
        )
        repo = ConnectorRepo(settings.repo, fs=self.ctx.fs)
        renderer = build_renderer(settings, fs=self.ctx.fs)
        runtime_vars, _runtime_sources = load_runtime_vars_with_sources(args, repo_root)
        options = options_from_args(args)

        env_files = select_manifest_paths(ctx=self.ctx, args=args, env=env, repo=repo)
        if not env_files:
            self.log.info("No connector manifests selected for drift")
            return 0

        router = ClusterRouter(
            settings=settings,
            env=env,
            cli_cluster=None,
            suppress_tag_conflicts=False,
            logger=lambda msg: self.log.warning("%s", msg),
        )
        env_files_by_cluster: dict[str, list[Path]] = {
            cluster: [] for cluster in selected_clusters
        }
        for path in env_files:
            rr = renderer.render(path, runtime_vars=runtime_vars)
            decision, _debug = router.route_with_debug(
                connector_name=rr.manifest.name,
                connectctl_meta=rr.connectctl,
                connectctl_sources=rr.connectctl_sources,
            )
            if decision.cluster_name in env_files_by_cluster:
                env_files_by_cluster[decision.cluster_name].append(path)

        cluster_reports: list[dict[str, object]] = []
        markdown_sections: list[str] = []
        has_drift = False
        fmt = resolve_output_format(args)

        for cluster_name in selected_clusters:
            target = self.ctx.connect_target(env, cluster_name)
            self.ctx.print_cluster_banner(target)
            cluster_env_files = env_files_by_cluster.get(cluster_name, [])
            if not cluster_env_files:
                self.log.info(
                    "No naturally routed manifests for drift env=%s cluster=%s",
                    env.value,
                    cluster_name,
                )
                cluster_reports.append(
                    {
                        "cluster": {
                            "group": target.cluster.name,
                            "env": target.cluster.env.value,
                            "urls": list(target.cluster.urls),
                        },
                        "counts": {
                            "manifests_checked": 0,
                            "ok": 0,
                            "drift": 0,
                            "missing": 0,
                        },
                        "detailed": [],
                    }
                )
                continue

            collected = collect_drift(
                policy_env=env,
                env_files=cluster_env_files,
                repo_root=repo_root,
                repo=repo,
                renderer=renderer,
                runtime_vars=runtime_vars,
                connect=target.client,
                config_test_runner=config_test_runner,
                strict_naming=options.strict_naming,
                policies=options.policies,
                naming=settings.naming,
                options=options,
                cluster_group=target.cluster.name,
                prune_config_keys=target.cluster.render_prune_config_keys,
                logger=self.log,
            )
            markdown_sections.append(
                build_drift_markdown(
                    env=env,
                    manifests_checked=collected.manifests_checked,
                    ok_count=collected.ok_count,
                    disabled_skipped=collected.disabled_skipped,
                    drift_count=collected.drift_count,
                    missing_count=collected.missing_count,
                    group_stats_dt=collected.group_stats_dt,
                    group_stats_dts=collected.group_stats_dts,
                    drift_key_counter=collected.drift_key_counter,
                    drift_override_source_counter=collected.drift_override_source_counter,
                    detailed=collected.detailed,
                    include_diffs=options.include_diffs,
                    max_lines=options.max_lines,
                    top_n=options.top_n,
                    tool_name=f"BKKT drift `{cluster_name}`",
                )
            )
            cluster_reports.append(
                {
                    "cluster": {
                        "group": target.cluster.name,
                        "env": target.cluster.env.value,
                        "urls": list(target.cluster.urls),
                    },
                    "counts": {
                        "manifests_checked": collected.manifests_checked,
                        "ok": collected.ok_count,
                        "drift": collected.drift_count,
                        "missing": collected.missing_count,
                    },
                    "detailed": collected.detailed,
                }
            )
            has_drift = has_drift or bool(
                collected.drift_count or collected.missing_count
            )

        md = "\n\n".join(markdown_sections).rstrip() + "\n"
        out_path = getattr(args, "output_file", None)
        if out_path:
            self.ctx.fs.write_text(Path(out_path), md, encoding="utf-8")

        if is_machine_output(fmt):
            write_payload(
                {
                    "command": "drift",
                    "comparison_mode": "post_prune",
                    "env": env.value,
                    "clusters": cluster_reports,
                    "options": {
                        "include_diffs": options.include_diffs,
                        "max_lines": options.max_lines,
                        "top": options.top_n,
                        "fail_on_drift": options.fail_on_drift,
                    },
                },
                fmt=fmt,
            )
            self.log.info("%s", md)
        else:
            write_text(md)

        if options.fail_on_drift and has_drift:
            return 2
        return 0
