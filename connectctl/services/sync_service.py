from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

from ..app.context import CliContext, ConnectTarget
from ..cli_helpers.clusters_arg import parse_clusters_selection
from ..cli_helpers.default_scope_ux import (
    confirm_broad_scope,
    effective_value,
    log_effective_values,
)
from ..cli_helpers.routing_explain import format_routing_explain_lines
from ..cli_helpers.timeout_args import timeout_seconds_from_args
from ..exceptions import ConfigError, ValidationError
from ..lifecycle.guards import log_disabled_manifest_skip
from ..kafka import KafkaMetricsClient
from ..logging_utils import get_logger
from ..models import ConnectorManifest, Environment
from ..rendering.factory import build_renderer
from ..rendering.runtime_vars import load_runtime_vars
from ..repo import ConnectorRepo
from ..routing import ClusterRouter
from ..syncing import compute_sync_plan, run_sync
from ..validation import ConfigTestRunner
from ..validation.manifest_validation import validate_manifest


class SyncService:
    """Reconcile an environment: apply all desired manifests, optionally prune remote connectors.

    Multi-cluster routing:
      - если `--cluster` НЕ задан, sync группирует коннекторы по routing (cluster group)
        и синхронизирует каждый кластер отдельно.
      - если `--clusters` задан, sync работает в multi-cluster режиме, но обрабатывает
        только выбранные cluster groups (filter-by-cluster, без override).
      - если `--cluster` задан, sync работает как раньше: один целевой cluster group (override).

    Важно: `--prune` применяется **внутри каждого кластера отдельно**.
    """

    def __init__(self, *, ctx: CliContext, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)

    def run(self, args) -> int:
        settings = self.ctx.settings
        repo_root = self.ctx.repo_root

        config_test_runner = ConfigTestRunner.from_settings(
            repo_root=repo_root, config_tests=settings.config_tests
        )

        env = self.ctx.env(getattr(args, "env", ""))

        cli_cluster = getattr(args, "cluster", None)
        clusters_filter_raw = getattr(args, "clusters", None)
        suppress_tag_conflicts = bool(getattr(args, "suppress_tag_conflicts", False))
        explain_routing = bool(getattr(args, "explain_routing", False))

        selected_clusters = parse_clusters_selection(
            clusters_filter_raw,
            available=settings.cluster_groups.keys(),
            allow_all_keyword=True,
        )
        if cli_cluster and selected_clusters is not None:
            raise ConfigError(
                "Нельзя использовать одновременно --cluster (override) и --clusters (filter)"
            )
        if selected_clusters is not None:
            missing = [c for c in selected_clusters if c not in settings.cluster_groups]
            if missing:
                raise ConfigError(
                    f"Unknown cluster group(s): {missing}. Available: {sorted(settings.cluster_groups.keys())}"
                )

        log_effective_values(
            self.log,
            command="sync",
            values=(
                effective_value(args, "env", env.value),
                effective_value(args, "cluster", cli_cluster or "-"),
                effective_value(
                    args,
                    "clusters",
                    ",".join(selected_clusters) if selected_clusters else "-",
                ),
                effective_value(args, "dry_run", bool(getattr(args, "dry_run", False))),
                effective_value(args, "prune", bool(getattr(args, "prune", False))),
            ),
        )

        if _requires_multi_cluster_confirmation(
            args,
            cli_cluster=cli_cluster,
            selected_clusters=selected_clusters,
        ):
            scope_label = (
                ",".join(selected_clusters)
                if selected_clusters
                else "natural-routing/all-clusters"
            )
            if not confirm_broad_scope(
                args,
                prompt=(
                    "Продолжить multi-cluster sync "
                    f"для env={env.value} scope={scope_label}?"
                ),
                logger=self.log,
            ):
                return 1

        router = ClusterRouter(
            settings=settings,
            env=env,
            cli_cluster=cli_cluster,
            suppress_tag_conflicts=suppress_tag_conflicts,
            logger=lambda msg: self.log.warning("%s", msg),
        )

        # Cache targets per cluster group.
        targets_by_cluster: Dict[str, ConnectTarget] = {}

        def _target(cluster_name: str) -> ConnectTarget:
            if cluster_name in targets_by_cluster:
                return targets_by_cluster[cluster_name]
            t = self.ctx.connect_target(env, cluster_name)
            targets_by_cluster[cluster_name] = t
            self.ctx.print_cluster_banner(t)
            return t

        repo = ConnectorRepo(settings.repo, fs=self.ctx.fs)
        renderer = build_renderer(
            settings,
            fs=self.ctx.fs,
            routing_cli_cluster=cli_cluster,
            routing_suppress_tag_conflicts=suppress_tag_conflicts,
        )
        runtime_vars = load_runtime_vars(args, repo_root)

        # Safety controls
        rollback_on_fail = getattr(args, "rollback_on_fail", None)
        if rollback_on_fail is None:
            rollback_on_fail = env in {Environment.stage, Environment.prod}
        connect_validate = bool(getattr(args, "connect_validate", True))

        # Render & validate all deployable manifests for the target environment.
        desired_by_cluster: Dict[str, List[ConnectorManifest]] = defaultdict(list)
        protected_disabled_by_cluster: Dict[str, List[str]] = defaultdict(list)
        disabled_skipped_by_cluster: Dict[str, int] = defaultdict(int)

        for env_file in repo.iter_deployable_manifests(env):
            rr = renderer.render(env_file, runtime_vars=runtime_vars)
            manifest = rr.manifest

            # Safety: should never happen for iter_deployable_manifests, but keep as guardrail.
            if manifest.info.env != env:
                raise ValidationError(
                    f"Unexpected env mismatch in repo manifests: {env_file} -> {manifest.info.env.value} (expected {env.value})"
                )

            decision, debug = router.route_with_debug(
                connector_name=manifest.name,
                connectctl_meta=rr.connectctl,
                connectctl_sources=rr.connectctl_sources,
            )
            if explain_routing:
                for line in format_routing_explain_lines(debug):
                    self.log.info("%s", line)

            if manifest.lifecycle.disabled:
                if selected_clusters is not None and decision.cluster_name not in set(
                    selected_clusters
                ):
                    continue
                log_disabled_manifest_skip(
                    manifest=manifest,
                    logger=self.log,
                    repo_root=repo_root,
                )
                protected_disabled_by_cluster[decision.cluster_name].append(
                    manifest.name
                )
                disabled_skipped_by_cluster[decision.cluster_name] += 1
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

            desired_by_cluster[decision.cluster_name].append(manifest)

        # Optional filter-by-cluster (без override): keep only natural manifests routed to chosen clusters.
        if selected_clusters is not None:
            allowed = set(selected_clusters)
            before_clusters = sorted(desired_by_cluster.keys())
            desired_by_cluster = defaultdict(
                list, {k: v for k, v in desired_by_cluster.items() if k in allowed}
            )
            after_clusters = sorted(desired_by_cluster.keys())
            if before_clusters != after_clusters:
                self.log.info(
                    "Cluster filter applied: requested=%s, before=%s, after=%s",
                    selected_clusters,
                    before_clusters,
                    after_clusters,
                )

        if not desired_by_cluster:
            if selected_clusters is not None:
                self.log.info(
                    "No deployable manifests for env=%s after cluster filter=%s",
                    env.value,
                    selected_clusters,
                )
            else:
                self.log.info("No deployable manifests for env=%s", env.value)
            return 0

        # Merge prune policy from config with CLI overrides.
        prune_cfg = settings.sync.prune
        allow_names = list(prune_cfg.allow_names) + list(
            getattr(args, "allow_name", None) or []
        )
        deny_names = list(prune_cfg.deny_names) + list(
            getattr(args, "deny_name", None) or []
        )
        allow_regexes = list(prune_cfg.allow_regex) + list(
            getattr(args, "allow_regex", None) or []
        )
        deny_regexes = list(prune_cfg.deny_regex) + list(
            getattr(args, "deny_regex", None) or []
        )

        rendered_dir = repo_root / "rendered" / env.value

        # Execute sync per cluster group.
        for cluster_name in sorted(desired_by_cluster.keys()):
            target = _target(cluster_name)
            cluster = target.cluster
            connect = target.client

            # Optional Kafka metrics client for post-deploy smoke checks.
            kafka_metrics: Optional[KafkaMetricsClient] = None
            if bool(getattr(args, "smoke", True)) and cluster.kafka is not None:
                try:
                    kafka_metrics = KafkaMetricsClient(cluster.kafka)
                except Exception as e:
                    self.log.warning(
                        "Kafka smoke checks отключены (не удалось инициализировать Kafka client) для cluster=%s: %s",
                        cluster_name,
                        e,
                    )
                    kafka_metrics = None

            desired = desired_by_cluster[cluster_name]
            existing = list(connect.list_connectors())

            plan = compute_sync_plan(
                env=env,
                desired=desired,
                existing_names=existing,
                protected_names=protected_disabled_by_cluster.get(cluster_name, ()),
                keep_name_regexes=getattr(args, "keep_regex", None) or [],
                prune=bool(getattr(args, "prune", False)),
                allow_names=allow_names,
                deny_names=deny_names,
                allow_regexes=allow_regexes,
                deny_regexes=deny_regexes,
            )

            self.log.info(
                "Sync plan env=%s cluster=%s: desired=%s existing=%s apply=%s prune=%s",
                env.value,
                cluster_name,
                len(plan.desired_names),
                len(plan.existing_names),
                len(plan.to_apply),
                len(plan.to_delete),
            )
            if plan.protected_names:
                self.log.info(
                    "Protected disabled connectors for cluster=%s: %s",
                    cluster_name,
                    ", ".join(plan.protected_names),
                )
            if disabled_skipped_by_cluster.get(cluster_name, 0):
                self.log.info(
                    "Disabled manifests skipped for cluster=%s: %s",
                    cluster_name,
                    disabled_skipped_by_cluster[cluster_name],
                )
            for n in plan.to_delete:
                self.log.info(" - prune[%s]: %s", cluster_name, n)

            run_sync(
                connect=connect,
                plan=plan,
                rendered_dir=rendered_dir,
                dry_run=bool(getattr(args, "dry_run", False)),
                wait_seconds=float(getattr(args, "wait_seconds", 10)),
                timeout_seconds=timeout_seconds_from_args(args, default=300.0),
                poll_interval_seconds=float(getattr(args, "poll_interval_seconds", 5)),
                connect_validate=connect_validate,
                rollback_on_fail=bool(rollback_on_fail),
                logger=self.log,
                skip_if_unchanged=bool(getattr(args, "skip_if_unchanged", True))
                and not bool(getattr(args, "force", False)),
                no_auto_catalog=not bool(getattr(args, "auto_catalog", True)),
                kafka=kafka_metrics,
                smoke=bool(getattr(args, "smoke", True)),
                smoke_strict=bool(getattr(args, "smoke_strict", False)),
            )

        return 0


def _requires_multi_cluster_confirmation(
    args,
    *,
    cli_cluster: Optional[str],
    selected_clusters: Optional[List[str]],
) -> bool:
    _ = selected_clusters
    if bool(getattr(args, "dry_run", False)):
        return False
    if cli_cluster:
        return False
    return True
