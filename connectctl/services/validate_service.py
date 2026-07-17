from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import List, Optional, Set

from ..app.context import CliContext
from ..exceptions import ValidationError
from ..git import diff_name_status, get_head_sha, guess_base_sha
from ..git_changes import expand_renames
from ..lifecycle.guards import log_disabled_manifest_skip
from ..logging_utils import get_logger
from ..models import Environment
from ..planning import Planner
from ..rendering.factory import build_renderer
from ..rendering.runtime_vars import load_runtime_vars
from ..repo import ConnectorRepo, LayerResolver
from ..repo.connector_dir_scope import infer_connector_dir_scope_from_path
from ..routing import ClusterRouter
from ..validation import (
    ConfigTestRunner,
    format_repo_layout_issues,
    lint_connector_dir_pattern,
)
from ..validation.manifest_validation import validate_manifest
from ..validation.schema_validation import (
    format_schema_issues,
    load_schema,
    validate_file,
)


class ValidateService:
    """Service for `connectctl validate`.

    Responsibilities:
    - repo-wide lint for connector_dir naming convention
    - optional strict JSON Schema validation (connectctl.yaml + manifest fragments)
    - render manifests and run basic validations (incl. optional strict naming)
    """

    def __init__(self, *, ctx: CliContext, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)

    def run(self, args) -> int:
        repo_root = self.ctx.repo_root
        settings = self.ctx.settings

        strict_connector_dir = bool(getattr(args, "strict_connector_dir", False))
        lint_scope = (
            str(getattr(args, "connector_dir_lint_scope", "all") or "all")
            .strip()
            .lower()
        )
        lint_max = int(getattr(args, "connector_dir_lint_max", 20) or 20)
        if lint_scope not in {"all", "changed"}:
            lint_scope = "all"

        strict_schema = bool(getattr(args, "strict_schema", False))
        strict_schema_max = int(getattr(args, "strict_schema_max", 20) or 20)

        env = Environment.from_str(args.env) if getattr(args, "env", None) else None

        # Compute git changes once if required.
        changes = None
        if bool(getattr(args, "changed", False)):
            base = getattr(args, "base", None) or guess_base_sha()
            head = getattr(args, "head", None) or get_head_sha()
            changes = diff_name_status(base, head, repo_root=repo_root)
            changes = expand_renames(changes)

        # --- Strict schema validation (fail-fast on connectctl.yaml)
        schema_issues = []
        validated_schema_files: Set[Path] = set()
        manifest_schema = None

        if strict_schema:
            connectctl_schema = self._load_schema_with_fallback(
                name="connectctl.schema.json",
                repo_root=repo_root,
            )
            manifest_schema = self._load_schema_with_fallback(
                name="manifest.schema.json",
                repo_root=repo_root,
            )

            schema_issues.extend(
                validate_file(
                    self.ctx.config_path, schema=connectctl_schema, fs=self.ctx.fs
                )
            )
            if schema_issues:
                raise ValidationError(
                    format_schema_issues(schema_issues, max_items=strict_schema_max)
                )

        connector_dir_issues, limited_scope = self._lint_connector_dirs(
            args=args,
            lint_scope=lint_scope,
            lint_max=lint_max,
            changes=changes,
        )

        # Proceed with manifest validation
        config_test_runner = ConfigTestRunner.from_settings(
            repo_root=repo_root, config_tests=settings.config_tests
        )

        repo = ConnectorRepo(settings.repo, fs=self.ctx.fs)
        renderer = build_renderer(settings, fs=self.ctx.fs)
        runtime_vars = load_runtime_vars(args, repo_root)
        disabled_skipped = 0
        validated = 0

        def validate_layers_schema(layers: tuple[Path, ...]) -> None:
            nonlocal schema_issues, validated_schema_files, manifest_schema, strict_schema
            if not strict_schema or manifest_schema is None:
                return
            for layer in layers:
                if layer in validated_schema_files:
                    continue
                if layer.suffix.lower() not in {".json", ".yaml", ".yml"}:
                    continue
                validated_schema_files.add(layer)
                schema_issues.extend(
                    validate_file(layer, schema=manifest_schema, fs=self.ctx.fs)
                )

        if bool(getattr(args, "changed", False)):
            assert changes is not None
            envs = (
                [env] if env else [Environment.dev, Environment.stage, Environment.prod]
            )
            for e in envs:
                planner = Planner(
                    repo=repo,
                    layer_resolver=LayerResolver(settings.repo, fs=self.ctx.fs),
                )
                plan = planner.plan(env=e, changes=changes, repo_root=repo_root)
                for p in plan.to_apply:
                    rr = renderer.render(p, runtime_vars=runtime_vars)
                    validate_layers_schema(rr.layers)
                    if rr.manifest.lifecycle.disabled:
                        log_disabled_manifest_skip(
                            manifest=rr.manifest,
                            logger=self.log,
                            repo_root=repo_root,
                        )
                        disabled_skipped += 1
                        continue
                    router = ClusterRouter(
                        settings=settings,
                        env=rr.manifest.info.env,
                        cli_cluster=None,
                        suppress_tag_conflicts=False,
                        logger=lambda msg: self.log.warning("%s", msg),
                    )
                    decision = router.route(
                        connector_name=rr.manifest.name,
                        connectctl_meta=rr.connectctl,
                    )
                    validate_manifest(
                        rr.manifest,
                        config_test_runner=config_test_runner,
                        config_test_context={
                            "cluster_group": decision.cluster_name,
                            "tags": list(rr.connectctl.get("tags") or []),
                        },
                        strict_naming=bool(getattr(args, "strict_naming", False)),
                        naming=settings.naming,
                        logger=self.log,
                    )
                    validated += 1
        else:
            for p in getattr(args, "paths", []) or []:
                rr = renderer.render(
                    (repo_root / p).resolve(), runtime_vars=runtime_vars
                )
                validate_layers_schema(rr.layers)
                if rr.manifest.lifecycle.disabled:
                    log_disabled_manifest_skip(
                        manifest=rr.manifest,
                        logger=self.log,
                        repo_root=repo_root,
                    )
                    disabled_skipped += 1
                    continue
                router = ClusterRouter(
                    settings=settings,
                    env=rr.manifest.info.env,
                    cli_cluster=None,
                    suppress_tag_conflicts=False,
                    logger=lambda msg: self.log.warning("%s", msg),
                )
                decision = router.route(
                    connector_name=rr.manifest.name,
                    connectctl_meta=rr.connectctl,
                )
                validate_manifest(
                    rr.manifest,
                    config_test_runner=config_test_runner,
                    config_test_context={
                        "cluster_group": decision.cluster_name,
                        "tags": list(rr.connectctl.get("tags") or []),
                    },
                    strict_naming=bool(getattr(args, "strict_naming", False)),
                    naming=settings.naming,
                    logger=self.log,
                )
                validated += 1

        if strict_schema and schema_issues:
            raise ValidationError(
                format_schema_issues(schema_issues, max_items=strict_schema_max)
            )

        if strict_connector_dir and connector_dir_issues:
            raise ValidationError(
                f"Repo layout lint failed: connector_dir не соответствует шаблону в {len(connector_dir_issues)} каталоге(ах). "
                "Исправьте имена директорий или уберите --strict-connector-dir."
            )

        if limited_scope:
            self.log.info(
                "✅ Repo layout lint (connector_dir, scope=changed): проверка выполнена."
            )

        self.log.info(
            "Validation OK (validated=%s, disabled_skipped=%s)",
            validated,
            disabled_skipped,
        )
        return 0

    def _load_schema_with_fallback(self, *, name: str, repo_root: Path) -> dict:
        """Load JSON schema from repo_root/schemas or fall back to package assets.

        This is important for the "two repos" setup:
        - BKKT is installed as a PyPI package
        - manifests live in a separate repository
        In that mode `schemas/` may be absent, but `bkkt validate --strict-schema`
        should still work.
        """

        local_path = (repo_root / "schemas" / name).resolve()
        if self.ctx.fs.exists(local_path):
            return load_schema(local_path, fs=self.ctx.fs)

        # Fallback: package resources.
        try:
            pkg_root = resources.files("connectctl.assets.repo_defaults")
            schema_res = pkg_root / "schemas" / name
            with resources.as_file(schema_res) as p:
                raw = Path(p).read_text(encoding="utf-8")
                return json.loads(raw)
        except Exception as e:
            raise ValidationError(
                f"Schema file not found: {local_path} (and built-in fallback missing): {e}"
            )

    def _lint_connector_dirs(
        self, *, args, lint_scope: str, lint_max: int, changes
    ) -> tuple[list, bool]:
        """Run repo layout lint for connector_dir.

        Returns: (issues, limited_scope)
        """

        settings = self.ctx.settings

        limit_to_paths: Optional[List[Path]] = None
        limited_scope = False

        if lint_scope == "changed":
            scope: set[Path] = set()

            if changes is not None:
                for ch in changes:
                    cand = infer_connector_dir_scope_from_path(
                        settings.repo, Path(ch.path)
                    )
                    if cand is not None:
                        scope.add(cand)

            elif getattr(args, "paths", None):
                for raw in args.paths:
                    cand = infer_connector_dir_scope_from_path(settings.repo, Path(raw))
                    if cand is not None:
                        scope.add(cand)

            limit_to_paths = sorted(scope, key=lambda x: x.as_posix())
            limited_scope = True

            if not limit_to_paths:
                # Keep logs explicit, but do not scan the whole repo.
                self.log.info(
                    "Repo layout lint (connector_dir, scope=changed): нет каталогов в области проверки."
                )
                issues = []
            else:
                issues = lint_connector_dir_pattern(
                    settings.repo, limit_to_paths=limit_to_paths
                )
        else:
            issues = lint_connector_dir_pattern(settings.repo)

        if issues:
            self.log.info("%s", format_repo_layout_issues(issues, max_items=lint_max))
        else:
            if lint_scope == "changed" and limit_to_paths:
                self.log.info(
                    "✅ Repo layout lint (connector_dir, scope=changed): проблем не найдено."
                )
            else:
                self.log.info(
                    "✅ Repo layout lint (connector_dir): проблем не найдено."
                )

        return issues, limited_scope
