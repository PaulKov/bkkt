from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import yaml

from ..app.context import CliContext, ConnectTarget
from ..cli_helpers.default_scope_ux import effective_value, log_effective_values
from ..cli_helpers.routing_explain import format_routing_explain_lines
from ..exceptions import ConfigError, ConnectApiError, ValidationError
from ..git import diff_name_status, get_head_sha, guess_base_sha
from ..git_changes import expand_renames
from ..lifecycle.guards import log_disabled_manifest_skip
from ..logging_utils import get_logger
from ..models import ConnectorManifest, Environment
from ..planning import Planner
from ..rendering.factory import build_renderer
from ..rendering.runtime_vars import load_runtime_vars
from ..rendering.unset_config import assert_final_config_has_no_nulls
from ..repo import ConnectorRepo, LayerResolver
from ..routing import ClusterRouter
from ..validation import ConfigTestRunner
from ..validation.manifest_validation import validate_manifest


_ENV_ORDER: Tuple[Environment, ...] = (
    Environment.dev,
    Environment.stage,
    Environment.prod,
)


@dataclass
class BulkValidateBucket:
    checked: int = 0
    passed: int = 0
    failed: int = 0
    disabled_skipped: int = 0
    accepted_local_exceptions: int = 0


@dataclass
class BulkValidateFailure:
    path: Path
    connector_name: str
    env: str
    cluster_name: str
    category: str
    reason: str


@dataclass
class BulkValidateSummary:
    total_checked: int = 0
    passed: int = 0
    failed: int = 0
    disabled_skipped: int = 0
    accepted_local_exceptions: int = 0
    per_env: Dict[str, BulkValidateBucket] = field(default_factory=dict)
    per_cluster: Dict[str, BulkValidateBucket] = field(default_factory=dict)
    failures: List[BulkValidateFailure] = field(default_factory=list)

    def record_success(
        self,
        *,
        env: str,
        cluster_name: str,
        accepted_local_exception: bool = False,
    ) -> None:
        self.total_checked += 1
        self.passed += 1
        self._bucket(self.per_env, env).checked += 1
        self._bucket(self.per_env, env).passed += 1
        self._bucket(self.per_cluster, cluster_name).checked += 1
        self._bucket(self.per_cluster, cluster_name).passed += 1
        if accepted_local_exception:
            self.accepted_local_exceptions += 1
            self._bucket(self.per_env, env).accepted_local_exceptions += 1
            self._bucket(self.per_cluster, cluster_name).accepted_local_exceptions += 1

    def record_failure(self, failure: BulkValidateFailure) -> None:
        self.total_checked += 1
        self.failed += 1
        self._bucket(self.per_env, failure.env).checked += 1
        self._bucket(self.per_env, failure.env).failed += 1
        self._bucket(self.per_cluster, failure.cluster_name).checked += 1
        self._bucket(self.per_cluster, failure.cluster_name).failed += 1
        self.failures.append(failure)

    def record_disabled(self, *, env: str, cluster_name: str) -> None:
        self.disabled_skipped += 1
        self._bucket(self.per_env, env).disabled_skipped += 1
        self._bucket(self.per_cluster, cluster_name).disabled_skipped += 1

    @staticmethod
    def _bucket(buckets: Dict[str, BulkValidateBucket], key: str) -> BulkValidateBucket:
        if key not in buckets:
            buckets[key] = BulkValidateBucket()
        return buckets[key]


@dataclass(frozen=True)
class PreparedValidationCandidate:
    path: Path
    env: Environment
    manifest: ConnectorManifest
    cluster_name: str
    connector_class: Optional[str]
    config_test_context: Dict[str, object]


@dataclass
class ValidateConnectService:
    """Сервис `connectctl validate-connect`.

    Валидирует финальные рендеры через Kafka Connect plugin validate endpoint:
      PUT /connector-plugins/<connector.class>/config/validate

    Side-effect отсутствует: коннекторы не создаются/не обновляются.

    Multi-cluster routing:
      - без `--all`: если `--cluster` НЕ задан, целевой кластер выбирается
        **для каждого коннектора** через routing (connectctl.cluster / tags /
        default_cluster); если задан — routing принудительно фиксируется этим
        cluster group;
      - с `--all`: `--cluster` работает как фильтр по normal routing
        (`cluster=all` — без фильтра).
    """

    ctx: CliContext
    logger: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        self.log = get_logger(self.logger or self.ctx.logger)

    def run(self, args) -> int:
        self._validate_cli_args(args)
        log_effective_values(
            self.log,
            command="validate-connect",
            values=(
                effective_value(args, "env", _effective_env_label(args)),
                effective_value(args, "cluster", _effective_cluster_label(args)),
                effective_value(args, "all", bool(getattr(args, "all", False))),
                effective_value(args, "changed", bool(getattr(args, "changed", False))),
                effective_value(args, "max_errors", getattr(args, "max_errors", None)),
            ),
        )
        if bool(getattr(args, "all", False)):
            return self._run_bulk(args)
        return self._run_selected(args)

    def _run_selected(self, args) -> int:
        repo_root = self.ctx.repo_root
        settings = self.ctx.settings
        env = self._parse_single_env(args)

        cli_cluster = self._normalize_cluster_name(getattr(args, "cluster", None))
        suppress_tag_conflicts = bool(getattr(args, "suppress_tag_conflicts", False))
        explain_routing = bool(getattr(args, "explain_routing", False))

        router = self._build_router(
            env=env,
            cli_cluster=cli_cluster,
            suppress_tag_conflicts=suppress_tag_conflicts,
        )
        target_cache: Dict[Tuple[str, Environment], ConnectTarget] = {}

        config_test_runner = ConfigTestRunner.from_settings(
            repo_root=repo_root, config_tests=settings.config_tests
        )

        repo = ConnectorRepo(settings.repo, fs=self.ctx.fs)
        renderer = build_renderer(
            settings,
            fs=self.ctx.fs,
            routing_cli_cluster=cli_cluster,
            routing_suppress_tag_conflicts=suppress_tag_conflicts,
        )
        runtime_vars = load_runtime_vars(args, repo_root)

        env_files = self._select_explicit_or_changed_files(
            args=args, env=env, repo=repo
        )
        if not env_files:
            self.log.info("Nothing to validate.")
            return 0

        max_errors = int(getattr(args, "max_errors", 20))
        strict_naming = bool(getattr(args, "strict_naming", False))
        disabled_skipped = 0
        validated = 0

        for path in env_files:
            candidate = self._prepare_candidate(
                path=path,
                env=env,
                renderer=renderer,
                runtime_vars=runtime_vars,
                router=router,
                explain_routing=explain_routing,
            )
            if candidate.manifest.lifecycle.disabled:
                log_disabled_manifest_skip(
                    manifest=candidate.manifest,
                    logger=self.log,
                    repo_root=repo_root,
                )
                disabled_skipped += 1
                continue
            self._run_local_manifest_validation(
                candidate=candidate,
                config_test_runner=config_test_runner,
                strict_naming=strict_naming,
            )
            self._run_connect_plugin_validation(
                candidate=candidate,
                max_errors=max_errors,
                target_cache=target_cache,
            )
            validated += 1

        self.log.info(
            "Kafka Connect plugin validation OK (validated=%s, disabled_skipped=%s)",
            validated,
            disabled_skipped,
        )
        return 0

    def _run_bulk(self, args) -> int:
        repo_root = self.ctx.repo_root
        settings = self.ctx.settings
        repo = ConnectorRepo(settings.repo, fs=self.ctx.fs)
        renderer = build_renderer(settings, fs=self.ctx.fs)
        runtime_vars = load_runtime_vars(args, repo_root)
        config_test_runner = ConfigTestRunner.from_settings(
            repo_root=repo_root, config_tests=settings.config_tests
        )

        envs = self._parse_bulk_envs(args)
        cluster_filter = self._parse_bulk_cluster_filter(args)
        max_errors = int(getattr(args, "max_errors", 20))
        strict_naming = bool(getattr(args, "strict_naming", False))
        explain_routing = bool(getattr(args, "explain_routing", False))
        suppress_tag_conflicts = bool(getattr(args, "suppress_tag_conflicts", False))

        target_cache: Dict[Tuple[str, Environment], ConnectTarget] = {}
        summary = BulkValidateSummary()

        for env in envs:
            router = self._build_router(
                env=env,
                cli_cluster=None,
                suppress_tag_conflicts=suppress_tag_conflicts,
            )
            for path in sorted(repo.iter_deployable_connector_files(env=env)):
                accepted_local_exception_reason: Optional[str] = None
                try:
                    candidate = self._prepare_candidate(
                        path=path,
                        env=env,
                        renderer=renderer,
                        runtime_vars=runtime_vars,
                        router=router,
                        explain_routing=explain_routing,
                    )
                except Exception as exc:  # pragma: no cover - summarized in tests
                    summary.record_failure(
                        BulkValidateFailure(
                            path=path,
                            connector_name=path.name,
                            env=env.value,
                            cluster_name="unresolved",
                            category="local-manifest",
                            reason=self._short_reason(exc),
                        )
                    )
                    continue

                if cluster_filter and candidate.cluster_name != cluster_filter:
                    continue
                if candidate.manifest.lifecycle.disabled:
                    log_disabled_manifest_skip(
                        manifest=candidate.manifest,
                        logger=self.log,
                        repo_root=repo_root,
                    )
                    summary.record_disabled(
                        env=env.value,
                        cluster_name=candidate.cluster_name,
                    )
                    continue

                try:
                    self._run_local_manifest_validation(
                        candidate=candidate,
                        config_test_runner=config_test_runner,
                        strict_naming=strict_naming,
                    )
                except Exception as exc:
                    accepted_local_exception_reason = (
                        self._accepted_local_manifest_exception_reason(
                            candidate=candidate,
                            exc=exc,
                        )
                    )
                    if accepted_local_exception_reason is None:
                        summary.record_failure(
                            BulkValidateFailure(
                                path=path,
                                connector_name=candidate.manifest.name,
                                env=env.value,
                                cluster_name=candidate.cluster_name,
                                category="local-manifest",
                                reason=self._short_reason(exc),
                            )
                        )
                        continue
                    self.log.info(
                        "ACCEPTED [local-manifest] env=%s cluster=%s connector=%s reason=%s",
                        env.value,
                        candidate.cluster_name,
                        candidate.manifest.name,
                        accepted_local_exception_reason,
                    )

                try:
                    self._run_connect_plugin_validation(
                        candidate=candidate,
                        max_errors=max_errors,
                        target_cache=target_cache,
                    )
                except ValidationError as exc:
                    summary.record_failure(
                        BulkValidateFailure(
                            path=path,
                            connector_name=candidate.manifest.name,
                            env=env.value,
                            cluster_name=candidate.cluster_name,
                            category="connect-plugin",
                            reason=self._short_reason(exc),
                        )
                    )
                    continue
                except ConnectApiError as exc:
                    summary.record_failure(
                        BulkValidateFailure(
                            path=path,
                            connector_name=candidate.manifest.name,
                            env=env.value,
                            cluster_name=candidate.cluster_name,
                            category="upstream-runtime",
                            reason=self._short_reason(exc),
                        )
                    )
                    continue
                except Exception as exc:  # pragma: no cover - summarized in tests
                    summary.record_failure(
                        BulkValidateFailure(
                            path=path,
                            connector_name=candidate.manifest.name,
                            env=env.value,
                            cluster_name=candidate.cluster_name,
                            category="unexpected",
                            reason=self._short_reason(exc),
                        )
                    )
                    continue

                summary.record_success(
                    env=env.value,
                    cluster_name=candidate.cluster_name,
                    accepted_local_exception=(
                        accepted_local_exception_reason is not None
                    ),
                )

        if summary.total_checked == 0 and summary.disabled_skipped == 0:
            env_label = ",".join(env.value for env in envs)
            cluster_label = cluster_filter or "all"
            self.log.info(
                "Nothing to validate for --all (env=%s, cluster=%s).",
                env_label,
                cluster_label,
            )
            return 0

        self._log_bulk_summary(summary, envs=envs)
        return 0 if summary.failed == 0 else 1

    def _validate_cli_args(self, args) -> None:
        is_bulk = bool(getattr(args, "all", False))
        env_arg = str(getattr(args, "env", "")).strip().lower()
        cluster_arg = self._normalize_cluster_name(getattr(args, "cluster", None))
        paths = list(getattr(args, "paths", []) or [])
        changed = bool(getattr(args, "changed", False))

        if is_bulk and changed:
            raise ConfigError("--all нельзя использовать вместе с --changed")
        if is_bulk and paths:
            raise ConfigError("--all нельзя использовать вместе с explicit paths")
        if not is_bulk and env_arg == "all":
            raise ConfigError("--env all поддерживается только вместе с --all")
        if not is_bulk and self._is_all_keyword(cluster_arg):
            raise ConfigError("--cluster all поддерживается только вместе с --all")

    def _parse_single_env(self, args) -> Environment:
        env_arg = str(getattr(args, "env", "")).strip().lower()
        try:
            return self.ctx.env(env_arg)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc

    def _parse_bulk_envs(self, args) -> List[Environment]:
        env_arg = str(getattr(args, "env", "")).strip().lower()
        if env_arg == "all":
            return list(_ENV_ORDER)
        try:
            return [self.ctx.env(env_arg)]
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc

    def _parse_bulk_cluster_filter(self, args) -> Optional[str]:
        cluster_arg = self._normalize_cluster_name(getattr(args, "cluster", None))
        if not cluster_arg or self._is_all_keyword(cluster_arg):
            return None
        if cluster_arg not in self.ctx.settings.cluster_groups:
            raise ConfigError(
                f"Unknown cluster group for --cluster: {cluster_arg!r}. "
                f"Expected one of: {', '.join(sorted(self.ctx.settings.cluster_groups)) or '<none>'}"
            )
        return cluster_arg

    @staticmethod
    def _normalize_cluster_name(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _is_all_keyword(value: Optional[str]) -> bool:
        return bool(value) and str(value).strip().lower() == "all"

    def _build_router(
        self,
        *,
        env: Environment,
        cli_cluster: Optional[str],
        suppress_tag_conflicts: bool,
    ) -> ClusterRouter:
        return ClusterRouter(
            settings=self.ctx.settings,
            env=env,
            cli_cluster=cli_cluster,
            suppress_tag_conflicts=suppress_tag_conflicts,
            logger=lambda msg: self.log.warning("%s", msg),
        )

    def _select_explicit_or_changed_files(
        self,
        *,
        args,
        env: Environment,
        repo: ConnectorRepo,
    ) -> List[Path]:
        repo_root = self.ctx.repo_root

        if bool(getattr(args, "changed", False)):
            base = getattr(args, "base", None) or guess_base_sha()
            head = getattr(args, "head", None) or get_head_sha()
            changes = diff_name_status(base, head, repo_root=repo_root)
            changes = expand_renames(changes)

            planner = Planner(
                repo=repo,
                layer_resolver=LayerResolver(self.ctx.settings.repo, fs=self.ctx.fs),
            )
            plan = planner.plan(env=env, changes=changes, repo_root=repo_root)
            env_files = sorted(plan.to_apply)
            self.log.info(
                "Computed validate-connect scope for env=%s from git diff %s..%s: %s manifest(s)",
                env.value,
                base,
                head,
                len(env_files),
            )
            return env_files

        return [((repo_root / p).resolve()) for p in (getattr(args, "paths", []) or [])]

    def _prepare_candidate(
        self,
        *,
        path: Path,
        env: Environment,
        renderer,
        runtime_vars,
        router: ClusterRouter,
        explain_routing: bool,
    ) -> PreparedValidationCandidate:
        rr = renderer.render(path, runtime_vars=runtime_vars)
        manifest = rr.manifest
        assert_final_config_has_no_nulls(
            manifest.config,
            connector_name=manifest.name,
            command="validate-connect",
        )

        if manifest.info.env != env:
            raise ValidationError(
                f"Refusing to validate manifest from env={manifest.info.env.value} while --env={env.value}: {path}"
            )

        decision, debug = router.route_with_debug(
            connector_name=manifest.name,
            connectctl_meta=rr.connectctl,
            connectctl_sources=rr.connectctl_sources,
        )
        if explain_routing:
            for line in format_routing_explain_lines(debug):
                self.log.info("%s", line)

        return PreparedValidationCandidate(
            path=path,
            env=env,
            manifest=manifest,
            cluster_name=decision.cluster_name,
            connector_class=manifest.config.get("connector.class"),
            config_test_context={
                "cluster_group": decision.cluster_name,
                "tags": list(rr.connectctl.get("tags") or []),
            },
        )

    def _run_local_manifest_validation(
        self,
        *,
        candidate: PreparedValidationCandidate,
        config_test_runner: ConfigTestRunner,
        strict_naming: bool,
    ) -> None:
        validate_manifest(
            candidate.manifest,
            config_test_runner=config_test_runner,
            config_test_context=candidate.config_test_context,
            strict_naming=strict_naming,
            naming=self.ctx.settings.naming,
            logger=self.log,
        )

    def _run_connect_plugin_validation(
        self,
        *,
        candidate: PreparedValidationCandidate,
        max_errors: int,
        target_cache: Dict[Tuple[str, Environment], ConnectTarget],
    ) -> None:
        connect = self._target(
            env=candidate.env,
            cluster_name=candidate.cluster_name,
            target_cache=target_cache,
        ).client
        connect.validate_manifest(candidate.manifest, max_errors=max_errors)
        self.log.info(
            "OK: %s (cluster=%s, connector.class=%s)",
            candidate.manifest.name,
            candidate.cluster_name,
            candidate.connector_class,
        )

    def _target(
        self,
        *,
        env: Environment,
        cluster_name: str,
        target_cache: Dict[Tuple[str, Environment], ConnectTarget],
    ) -> ConnectTarget:
        key = (cluster_name, env)
        if key in target_cache:
            return target_cache[key]
        target = self.ctx.connect_target(env, cluster_name)
        target_cache[key] = target
        self.ctx.print_cluster_banner(target)
        return target

    def _log_bulk_summary(
        self,
        summary: BulkValidateSummary,
        *,
        envs: Iterable[Environment],
    ) -> None:
        self.log.info(
            "Kafka Connect bulk validation summary: checked=%s passed=%s failed=%s accepted_local_exceptions=%s",
            summary.total_checked,
            summary.passed,
            summary.failed,
            summary.accepted_local_exceptions,
        )
        self.log.info(
            "  lifecycle: disabled_skipped=%s",
            summary.disabled_skipped,
        )

        for env in envs:
            bucket = summary.per_env.get(env.value)
            if not bucket:
                continue
            self.log.info(
                "  env=%s checked=%s passed=%s failed=%s accepted_local_exceptions=%s",
                env.value,
                bucket.checked,
                bucket.passed,
                bucket.failed,
                bucket.accepted_local_exceptions,
            )
            self.log.info(
                "    lifecycle env=%s disabled_skipped=%s",
                env.value,
                bucket.disabled_skipped,
            )

        for cluster_name in sorted(summary.per_cluster):
            bucket = summary.per_cluster[cluster_name]
            self.log.info(
                "  cluster=%s checked=%s passed=%s failed=%s accepted_local_exceptions=%s",
                cluster_name,
                bucket.checked,
                bucket.passed,
                bucket.failed,
                bucket.accepted_local_exceptions,
            )
            self.log.info(
                "    lifecycle cluster=%s disabled_skipped=%s",
                cluster_name,
                bucket.disabled_skipped,
            )

        for failure in summary.failures:
            self.log.error(
                "FAIL [%s] env=%s cluster=%s connector=%s path=%s reason=%s",
                failure.category,
                failure.env,
                failure.cluster_name,
                failure.connector_name,
                failure.path,
                failure.reason,
            )

    @staticmethod
    def _short_reason(exc: Exception) -> str:
        text = str(exc).strip() or exc.__class__.__name__
        return text.splitlines()[0]

    def _accepted_local_manifest_exception_reason(
        self,
        *,
        candidate: PreparedValidationCandidate,
        exc: Exception,
    ) -> Optional[str]:
        if not isinstance(exc, ValidationError):
            return None
        if not str(exc).startswith("Config contains name="):
            return None

        drift_path = candidate.path.parent / "export" / "drift.yaml"
        if not drift_path.exists():
            return None

        try:
            payload = yaml.safe_load(drift_path.read_text(encoding="utf-8")) or {}
        except Exception:  # pragma: no cover - defensive fallback
            return None
        if not isinstance(payload, dict):
            return None
        if payload.get("status") != "accepted_drift":
            return None
        if payload.get("connector_name_repo") != candidate.manifest.name:
            return None
        if candidate.manifest.config.get("name") != payload.get("connector_name_live"):
            return None

        entries = payload.get("accepted_drift") or []
        if not isinstance(entries, list):
            return None

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("key") != "connector.name":
                continue
            if entry.get("repo_render_value") != candidate.manifest.name:
                continue
            if entry.get("live_value") != candidate.manifest.config.get("name"):
                continue
            reason = str(entry.get("reason") or "").strip()
            return (
                reason
                or "documented legacy connector.name exception from export/drift.yaml"
            )

        return None


def _effective_env_label(args) -> str:
    env_arg = str(getattr(args, "env", "")).strip().lower()
    return env_arg or "-"


def _effective_cluster_label(args) -> str:
    cluster_arg = getattr(args, "cluster", None)
    if cluster_arg is None:
        return "all" if bool(getattr(args, "all", False)) else "routing/default"
    normalized = str(cluster_arg).strip()
    if normalized:
        return normalized
    return "all" if bool(getattr(args, "all", False)) else "routing/default"
