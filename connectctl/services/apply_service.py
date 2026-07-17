from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

from ..app.context import CliContext
from ..exceptions import ValidationError
from ..lifecycle.guards import log_disabled_manifest_skip, raise_if_manifest_disabled
from ..logging_utils import get_logger
from ..models import Environment
from ..repo import ConnectorRepo
from ..repo.apply_targets.models import ApplyItem
from ..validation import ConfigTestRunner

from ..cli_helpers.routing_explain import format_routing_explain_lines
from ..rendering.prune import apply_prune_to_manifest
from ..routing import ClusterRouter

from ..adapters.filesystem_threadsafe import ThreadSafeFileSystem
from ..execution import ConcurrencyOptions, RateLimiter, map_fail_fast

from ..rendering.factory import build_renderer
from ..validation.manifest_validation import validate_manifest
from ..rendering.runtime_vars import load_runtime_vars_with_sources
from ..rendering.unset_config import assert_final_config_has_no_nulls
from .failure_bundle import FailureBundleWriter

from .apply.artifacts import RenderedArtifactLoader
from .apply.deployer import ApplyOptions, ConnectorDeployer
from .apply.deletions import apply_deletions
from .apply.initial_only_shared_topic_guard import (
    enforce_initial_only_shared_topic_guard,
)
from .apply.kafka_smoke import build_kafka_metrics_client
from .apply.manifest_loader import load_manifest_for_item
from .apply.plan_builder import build_apply_plan
from .apply.vars_preflight import (
    ApplyVarsPreflightOptions,
    run_apply_vars_preflight,
)


@dataclass
class ApplyService:
    """High-level service for `connectctl apply`.

    Refactor stage 11:
    - heavy logic split into small modules under `connectctl.services.apply.*`
    - this service acts as an orchestrator and keeps the CLI adapter small.

    Dependencies are injected via :class:`connectctl.app.context.CliContext`.
    Logger is optional (DI-friendly) and defaults to the BKKT logger.
    """

    ctx: CliContext
    logger: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        self.log = get_logger(self.logger or self.ctx.logger)

    def run(self, args) -> int:
        repo_root = self.ctx.repo_root
        settings = self.ctx.settings

        env = self.ctx.env(getattr(args, "env"))

        conc = ConcurrencyOptions.from_args(args)
        throttle = (
            RateLimiter(conc.rate_limit_per_second, burst=conc.burst)
            if conc.rate_limit_per_second > 0
            else None
        )

        # Cluster routing is per-connector. We keep Connect clients/deployers per cluster lazily.
        router = ClusterRouter(
            settings=settings,
            env=env,
            cli_cluster=getattr(args, "cluster", None),
            suppress_tag_conflicts=bool(getattr(args, "suppress_tag_conflicts", False)),
            logger=lambda msg: self.log.warning("%s", msg),
        )

        config_test_runner = ConfigTestRunner.from_settings(
            repo_root=repo_root, config_tests=settings.config_tests
        )

        # If we run in parallel, protect FS operations (in-memory FS / concurrent writes).
        fs = ThreadSafeFileSystem(self.ctx.fs) if conc.jobs > 1 else self.ctx.fs
        failure_bundle_writer = FailureBundleWriter.from_args(
            command="apply", repo_root=repo_root, fs=fs, args=args
        )

        repo = ConnectorRepo(settings.repo, fs=fs)
        renderer = build_renderer(
            settings,
            fs=fs,
            routing_cli_cluster=getattr(args, "cluster", None),
            routing_suppress_tag_conflicts=bool(
                getattr(args, "suppress_tag_conflicts", False)
            ),
        )
        runtime_vars, runtime_sources = load_runtime_vars_with_sources(args, repo_root)

        # Optional artifact-based deploy: load rendered connector configs from a directory.
        artifact_loader = RenderedArtifactLoader.from_args(
            args, repo_root=repo_root, repo=repo, fs=fs
        )

        plan = build_apply_plan(
            args=args,
            env=env,
            repo_root=repo_root,
            repo=repo,
            repo_config=settings.repo,
            logger=self.log,
        )

        if plan.is_empty:
            self.log.info("Nothing to do.")
            return 0

        rendered_dir = (repo_root / "rendered" / env.value).resolve()

        options = ApplyOptions.from_args(args, env=env)

        # Render/apply flags
        reuse_overrides = bool(getattr(args, "reuse_overrides", True))
        reuse_from_raw = getattr(args, "reuse_from", None) or []
        reuse_from = [Path(p) for p in reuse_from_raw] or None
        print_config = bool(getattr(args, "print_config", True))
        explain_routing = bool(getattr(args, "explain_routing", False))
        explicit_mode = not bool(getattr(args, "changed", False))

        # Smoke checks are best-effort and depend on Kafka settings (may be absent).
        smoke_enabled = bool(getattr(args, "smoke", True))

        # Connect clients / deployers are created lazily per target cluster group.
        _deployer_lock = Lock()
        _targets: Dict[str, Any] = {}
        _deployers: Dict[str, ConnectorDeployer] = {}

        # HTTP read timeout for PUT/validate (Kafka Connect may connect to DB and take >30s).
        request_timeout_s = options.timeout_seconds
        connect_timeout = (5.0, request_timeout_s)

        def _get_target(cluster_name: str):
            with _deployer_lock:
                target = _targets.get(cluster_name)
                if target is None:
                    _assert_runtime_write_allowed(
                        self.ctx,
                        env=env,
                        cluster_name=cluster_name,
                        command="apply",
                        dry_run=options.dry_run,
                        unsafe=bool(getattr(args, "runtime_unsafe_rest", False)),
                    )
                    target = self.ctx.connect_target(
                        env, cluster_name, throttle=throttle, timeout=connect_timeout
                    )
                    self.ctx.print_cluster_banner(target)
                    _targets[cluster_name] = target
                return target

        def _get_deployer(cluster_name: str) -> ConnectorDeployer:
            with _deployer_lock:
                dep = _deployers.get(cluster_name)
                if dep is not None:
                    return dep

                # Ensure target exists (and banner printed) exactly once per cluster group.
                target = _targets.get(cluster_name)
                if target is None:
                    _assert_runtime_write_allowed(
                        self.ctx,
                        env=env,
                        cluster_name=cluster_name,
                        command="apply",
                        dry_run=options.dry_run,
                        unsafe=bool(getattr(args, "runtime_unsafe_rest", False)),
                    )
                    target = self.ctx.connect_target(
                        env, cluster_name, throttle=throttle, timeout=connect_timeout
                    )
                    self.ctx.print_cluster_banner(target)
                    _targets[cluster_name] = target

                kafka_metrics = build_kafka_metrics_client(
                    target.cluster, enabled=smoke_enabled, logger=self.log
                )
                dep = ConnectorDeployer(
                    connect=target.client,
                    rendered_dir=rendered_dir,
                    options=options,
                    kafka_metrics=kafka_metrics,
                    schema_preflight_allowlist=tuple(
                        item
                        for item in (
                            settings.schema_registry_preflight.get("allowlist", [])
                            if isinstance(settings.schema_registry_preflight, dict)
                            else []
                        )
                        if isinstance(item, dict)
                    ),
                    fs=fs,
                    logger=self.log,
                )
                _deployers[cluster_name] = dep
                return dep

        def _get_connect(cluster_name: str):
            return _get_target(cluster_name).client

        show_vars = bool(getattr(args, "show_vars", True))

        def _routing_payload_from_decision(decision) -> dict[str, object]:
            return {
                "cluster": {
                    "group": decision.cluster.name,
                    "env": env.value,
                    "urls": list(decision.cluster.urls),
                },
                "source": decision.source,
                "target": f"{decision.cluster.name}/{env.value}",
            }

        def _apply_one(item: ApplyItem) -> str:
            stage = "load_manifest"
            loaded = None
            decision = None
            routing_debug = None
            manifest = None
            pruned_keys: tuple[str, ...] = ()

            try:
                requested_info = repo.parse_connector_path(
                    item.requested_path, must_exist=False
                )
                if requested_info.env != env:
                    raise ValidationError(
                        f"Manifest env mismatch: target --env={env.value}, but file is {requested_info.env.value}: "
                        f"{item.requested_path}"
                    )

                loaded = load_manifest_for_item(
                    item=item,
                    manifest_path=item.actual_path,
                    repo_root=repo_root,
                    repo=repo,
                    renderer=renderer,
                    runtime_vars=runtime_vars,
                    runtime_var_sources=runtime_sources,
                    reuse_overrides=reuse_overrides,
                    reuse_from=reuse_from,
                    artifact_loader=artifact_loader,
                    show_vars=show_vars,
                    logger=self.log,
                )

                if loaded.manifest.info.env != env:
                    raise ValidationError(
                        f"Manifest env mismatch: target --env={env.value}, but file is {loaded.manifest.info.env.value}: "
                        f"{item.requested_path}"
                    )

                stage = "route"
                decision, routing_debug = router.route_with_debug(
                    connector_name=loaded.manifest.name,
                    connectctl_meta=loaded.connectctl,
                    connectctl_sources=loaded.connectctl_sources,
                )
                if explain_routing:
                    self.log.info("Target cluster (routing): %s", decision.cluster.name)
                    for line in format_routing_explain_lines(routing_debug):
                        self.log.info("%s", line)

                manifest = loaded.manifest
                if manifest.lifecycle.disabled:
                    stage = "lifecycle"
                    if explicit_mode:
                        raise_if_manifest_disabled(
                            manifest=manifest,
                            logger=self.log,
                            repo_root=repo_root,
                            command="apply",
                        )
                    log_disabled_manifest_skip(
                        manifest=manifest,
                        logger=self.log,
                        repo_root=repo_root,
                    )
                    return ""
                if decision.cluster.render_prune_config_keys:
                    manifest, pruned_keys = apply_prune_to_manifest(
                        manifest, decision.cluster.render_prune_config_keys
                    )
                    if pruned_keys:
                        self.log.info(
                            "Cluster render policy: pruned %d config keys for %s",
                            len(pruned_keys),
                            decision.cluster.name,
                        )

                assert_final_config_has_no_nulls(
                    manifest.config,
                    connector_name=manifest.name,
                    command="apply",
                )

                if print_config:
                    if loaded.unset_config_keys:
                        self.log.info(
                            "Unset inherited keys, not sent to Kafka Connect (%s): %s",
                            decision.cluster.name,
                            ", ".join(sorted(loaded.unset_config_keys)),
                        )
                    payload = {"name": manifest.name, "config": manifest.config}
                    self.log.info(
                        "Final connector config (%s):\n%s",
                        decision.cluster.name,
                        json.dumps(
                            payload, indent=2, sort_keys=True, ensure_ascii=False
                        ),
                    )

                if show_vars and runtime_vars:
                    vars_used = ", ".join(sorted(runtime_vars.keys()))
                    self.log.info("vars in use: %s", vars_used)

                stage = "vars_preflight"
                run_apply_vars_preflight(
                    settings=settings,
                    manifest=manifest,
                    provider_context=loaded.provider_context,
                    options=ApplyVarsPreflightOptions(
                        enabled=options.vars_preflight,
                        reason=options.vars_preflight_reason,
                        provider_contracts=options.vars_preflight_provider_contracts,
                        secret_index=options.vars_preflight_secret_index,
                    ),
                    logger=self.log,
                )

                stage = "local_validate"
                validate_manifest(
                    manifest,
                    config_test_runner=config_test_runner,
                    config_test_context={
                        "cluster_group": decision.cluster_name,
                        "tags": list(loaded.connectctl.get("tags") or []),
                    },
                    strict_naming=bool(getattr(args, "strict_naming", True)),
                    policies=bool(getattr(args, "policies", True)),
                    policy_env=env,
                    policy_layers=loaded.layers,
                    naming=settings.naming,
                    logger=self.log,
                )

                if not options.dry_run:
                    stage = "initial_only_shared_topic_guard"
                    enforce_initial_only_shared_topic_guard(
                        connect=_get_connect(decision.cluster.name),
                        manifest=manifest,
                        logger=self.log,
                    )

                stage = "deploy"
                deployer = _get_deployer(decision.cluster.name)
                deployer.deploy(
                    manifest,
                    loaded_from_artifact=loaded.loaded_from_artifact,
                    connectctl_meta=loaded.connectctl,
                )
                return manifest.name
            except Exception as exc:
                manifest_meta = {
                    "requested_path": str(item.requested_path),
                    "path": str(item.actual_path),
                }
                if manifest is not None:
                    manifest_meta["name"] = manifest.name
                    manifest_meta["path"] = str(manifest.source_path)
                if decision is not None:
                    manifest_meta["cluster_group"] = decision.cluster.name

                prepared_manifest = (
                    {"name": manifest.name, "config": manifest.config}
                    if manifest is not None
                    else None
                )
                routing_payload = (
                    _routing_payload_from_decision(decision)
                    if decision is not None
                    else None
                )
                failure_bundle_writer.write(
                    env=env.value,
                    stage=stage,
                    error=exc,
                    manifest_meta=manifest_meta,
                    prepared_manifest=prepared_manifest,
                    routing_payload=routing_payload,
                    routing_debug=routing_debug,
                    pruned_config_keys=pruned_keys,
                    extra={
                        "name": manifest.name if manifest is not None else None,
                        "cluster_group": (
                            decision.cluster.name if decision is not None else None
                        ),
                    },
                )
                raise

        if conc.jobs <= 1:
            for item in plan.apply_items:
                _apply_one(item)
        else:
            applied_names = map_fail_fast(plan.apply_items, _apply_one, jobs=conc.jobs)
            applied_names = [n for n in applied_names if n]
            self.log.info(
                "Applied %s connector(s) in parallel (--jobs=%s)",
                len(applied_names),
                conc.jobs,
            )

        # Handle deletions (desired state) from --changed plan.
        apply_deletions(
            delete_rels=plan.delete_rels,
            repo_root=repo_root,
            base_ref=plan.base_ref,
            settings=settings,
            router=router,
            get_connect=_get_connect,
            renderer=renderer,
            runtime_vars=runtime_vars,
            runtime_var_sources=runtime_sources,
            reuse_overrides=reuse_overrides,
            reuse_from=reuse_from,
            dry_run=options.dry_run,
            logger=self.log,
        )

        return 0


def _assert_runtime_write_allowed(
    ctx: CliContext,
    *,
    env: Environment,
    cluster_name: str,
    command: str,
    dry_run: bool,
    unsafe: bool,
) -> None:
    if dry_run:
        return
    guard = getattr(ctx, "assert_rest_mutation_allowed", None)
    if callable(guard):
        guard(env, cluster_name, command=command, unsafe=unsafe)
