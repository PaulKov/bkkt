from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from ...app.context import CliContext, ConnectTarget
from ...cli_helpers.routing_explain import format_routing_explain_lines
from ...comparison import compare_connector_configs
from ...diffing import summarize_diff
from ...exceptions import ValidationError
from ...lifecycle.guards import log_disabled_manifest_skip
from ...logging_utils import get_logger
from ...models import Environment
from ...output import (
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
)
from ...rendering.factory import build_renderer
from ...rendering.prune import apply_prune_to_render_result
from ...rendering.runtime_vars import load_runtime_vars_with_sources, log_vars_used
from ...routing import ClusterRouter
from ...validation import ConfigTestRunner
from ...validation.manifest_validation import validate_manifest

from .markdown import build_diff_markdown
from .models import DisabledItem, DriftItem, MissingItem
from .path_utils import relpath_safe
from .payload import build_diff_payload
from .selection import select_env_files


class DiffService:
    """Сервис для команды `connectctl diff`.

    Задача:
      - выбрать набор manifest-файлов (по `--changed` или явным путям, иначе — весь env)
      - отрендерить desired config
      - сравнить его с live config из Kafka Connect
      - собрать markdown-отчёт

    Multi-cluster routing:
      - целевой кластер выбирается **для каждого коннектора** через `ClusterRouter`
        (connectctl.cluster / tags / default_cluster / CLI override).
      - diff сравнивает desired vs live конфиг в соответствующем cluster group.
    """

    def __init__(self, *, ctx: CliContext, logger=None) -> None:
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)

    def run(self, args) -> int:
        repo_root = self.ctx.repo_root
        settings = self.ctx.settings

        env = Environment.from_str(args.env)

        # Routing config
        cli_cluster = getattr(args, "cluster", None)
        suppress_tag_conflicts = bool(getattr(args, "suppress_tag_conflicts", False))
        explain_routing = bool(getattr(args, "explain_routing", False))

        router = ClusterRouter(
            settings=settings,
            env=env,
            cli_cluster=cli_cluster,
            suppress_tag_conflicts=suppress_tag_conflicts,
            logger=lambda msg: self.log.warning("%s", msg),
        )

        renderer = build_renderer(
            settings,
            fs=self.ctx.fs,
            routing_cli_cluster=cli_cluster,
            routing_suppress_tag_conflicts=suppress_tag_conflicts,
        )
        repo = renderer.repo

        runtime_vars, runtime_sources = load_runtime_vars_with_sources(args, repo_root)
        config_test_runner = ConfigTestRunner.from_settings(
            repo_root=repo_root, config_tests=settings.config_tests
        )

        env_files = select_env_files(
            args,
            env=env,
            repo_root=repo_root,
            repo=repo,
            layer_resolver=renderer.layers,
        )

        if not env_files:
            self.log.info("No connector manifests selected for diff")
            return 0

        # Cache targets per cluster group to avoid re-creating clients.
        targets_by_cluster: Dict[str, ConnectTarget] = {}

        def _target(cluster_name: str) -> ConnectTarget:
            if cluster_name in targets_by_cluster:
                return targets_by_cluster[cluster_name]
            t = self.ctx.connect_target(env, cluster_name)
            targets_by_cluster[cluster_name] = t
            # UX: show banner once per cluster
            self.ctx.print_cluster_banner(t)
            return t

        max_lines = int(getattr(args, "max_lines", 200))

        drifted: List[DriftItem] = []
        disabled: List[DisabledItem] = []
        missing: List[MissingItem] = []

        # Per-cluster counters
        checked_by_cluster: Dict[str, int] = defaultdict(int)
        clean_by_cluster: Dict[str, int] = defaultdict(int)
        disabled_by_cluster: Dict[str, int] = defaultdict(int)
        drift_by_cluster: Dict[str, int] = defaultdict(int)
        missing_by_cluster: Dict[str, int] = defaultdict(int)

        for p in env_files:
            rr = renderer.render(
                p, runtime_vars=runtime_vars, runtime_var_sources=runtime_sources
            )
            if bool(getattr(args, "show_vars", True)):
                log_vars_used(rr, repo_root, logger=self.log)

            manifest = rr.manifest

            # Safety: env-file should match --env
            if manifest.info.env != env:
                raise ValidationError(
                    f"Refusing to diff manifest from env={manifest.info.env.value} while --env={env.value}: {p}"
                )

            decision, debug = router.route_with_debug(
                connector_name=manifest.name,
                connectctl_meta=rr.connectctl,
                connectctl_sources=rr.connectctl_sources,
            )

            if explain_routing:
                for line in format_routing_explain_lines(debug):
                    self.log.info("%s", line)

            cluster_name = decision.cluster_name
            if manifest.lifecycle.disabled:
                log_disabled_manifest_skip(
                    manifest=manifest,
                    logger=self.log,
                    repo_root=repo_root,
                )
                disabled.append(
                    DisabledItem(
                        name=manifest.name,
                        cluster=cluster_name,
                        manifest_rel=relpath_safe(p, base=repo_root),
                        reason=manifest.lifecycle.reason or "disabled",
                        ticket=manifest.lifecycle.ticket,
                        until=manifest.lifecycle.until,
                    )
                )
                disabled_by_cluster[cluster_name] += 1
                continue

            validate_manifest(
                manifest,
                config_test_runner=config_test_runner,
                config_test_context={
                    "cluster_group": decision.cluster_name,
                    "tags": list(rr.connectctl.get("tags") or []),
                },
                strict_naming=bool(getattr(args, "strict_naming", True)),
                policies=bool(getattr(args, "policies", True)),
                policy_env=env,
                policy_layers=rr.layers,
                naming=settings.naming,
                logger=self.log,
            )
            checked_by_cluster[cluster_name] += 1

            connect = _target(cluster_name).client

            pruned_keys: tuple[str, ...] = ()
            if decision.cluster.render_prune_config_keys:
                rr, pruned_keys = apply_prune_to_render_result(
                    rr, decision.cluster.render_prune_config_keys
                )
                manifest = rr.manifest

            live_cfg = connect.get_config_optional(manifest.name)
            if live_cfg is None:
                missing.append(MissingItem(name=manifest.name, cluster=cluster_name))
                missing_by_cluster[cluster_name] += 1
                continue

            comparison = compare_connector_configs(
                connector_name=manifest.name,
                desired=manifest.config,
                actual=live_cfg,
            )

            if comparison.in_sync:
                clean_by_cluster[cluster_name] += 1
                continue

            diff_txt = comparison.unified_diff
            diff_txt, trimmed = summarize_diff(diff_txt, max_lines=max_lines)
            rel = relpath_safe(p, base=repo_root)
            drifted.append(
                DriftItem(
                    name=manifest.name,
                    cluster=cluster_name,
                    diff=diff_txt,
                    trimmed=trimmed,
                    manifest_rel=rel,
                    pruned_config_keys=pruned_keys,
                    diff_keys=comparison.changed_keys,
                )
            )
            drift_by_cluster[cluster_name] += 1

        total_checked = len(env_files)
        total_clean = int(sum(clean_by_cluster.values()))

        # Prepare cluster summary for markdown/payload.
        all_clusters = sorted(
            set(checked_by_cluster.keys())
            | set(targets_by_cluster.keys())
            | set(disabled_by_cluster.keys())
        )
        cluster_stats: Dict[str, Dict[str, int]] = {}
        for c in all_clusters:
            cluster_stats[c] = {
                "checked": int(checked_by_cluster.get(c, 0)),
                "clean": int(clean_by_cluster.get(c, 0)),
                "disabled": int(disabled_by_cluster.get(c, 0)),
                "drifted": int(drift_by_cluster.get(c, 0)),
                "missing": int(missing_by_cluster.get(c, 0)),
            }

        md = build_diff_markdown(
            env=env,
            total=total_checked,
            clean=total_clean,
            disabled=disabled,
            missing=missing,
            drifted=drifted,
            cluster_stats=cluster_stats,
        )

        fmt = resolve_output_format(args)
        if is_machine_output(fmt):
            payload = build_diff_payload(
                env=env,
                targets_by_cluster=targets_by_cluster,
                cluster_stats=cluster_stats,
                manifests_checked=total_checked,
                clean=total_clean,
                disabled=disabled,
                missing=missing,
                drifted=drifted,
            )
            write_payload(payload, fmt=fmt)

            # Markdown оставляем в логах (stderr), чтобы stdout был машинно-читаемым.
            self.log.info("%s", md)
        else:
            write_text(md)

        if bool(getattr(args, "fail_on_drift", False)) and (missing or drifted):
            return 2
        return 0
