from __future__ import annotations

from pathlib import Path
from typing import Any

from ..exceptions import ConnectCtlError
from ..function_contracts import FunctionContractLoader, FunctionContractRunner
from ..function_locks import FunctionLockService
from ..rendering.factory import build_renderer
from ..settings_models import Settings
from ..template_impact import TemplateImpactService
from ..template_runtime import FunctionContext, TemplateRuntime
from ..vars_contracts import VarsSchemaEntry, VarsSchemaLoader
from .models import ReviewChecklistItem


class FunctionReviewService:
    """Builds a single review payload for repo-local function changes."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repo_root = settings.repo.root.resolve()

    def review(
        self,
        name: str,
        *,
        with_render_diff: bool = False,
        contract_pattern: str | None = None,
        lock_file: Path | None = None,
    ) -> dict[str, Any]:
        runtime = TemplateRuntime.from_settings(self.settings)
        descriptor = runtime.registry.get(name)
        impact = TemplateImpactService(self.settings).function_impact(
            name,
            with_render_diff=with_render_diff,
            metadata={"function": descriptor.to_payload()},
        )
        cases = tuple(
            case
            for case in FunctionContractLoader(
                self.repo_root, pattern=contract_pattern
            ).load()
            if case.function == name
        )
        contracts = FunctionContractRunner(
            runtime,
            context_factory=self._function_context_from_manifest,
        ).run(cases)
        contracts_payload = contracts.to_payload()
        if not cases:
            contracts_payload["status"] = "missing"
        lock_payload = self._lock_payload(lock_file)
        checklist = _function_checklist(
            contracts_payload=contracts_payload,
            impact_payload=impact.to_payload(),
            lock_payload=lock_payload,
        )
        status = (
            "failed" if any(item.status == "failed" for item in checklist) else "ok"
        )
        return {
            "kind": "function_review",
            "status": status,
            "function": descriptor.to_payload(),
            "contracts": contracts_payload,
            "impact": impact.to_payload(),
            "lock": lock_payload,
            "checklist": [item.to_payload() for item in checklist],
        }

    def _function_context_from_manifest(self, manifest: str | None) -> FunctionContext:
        if not manifest:
            return FunctionContext.from_flat_context({}, repo_root=self.repo_root)
        path = Path(manifest)
        if not path.is_absolute():
            path = self.repo_root / path
        rr = build_renderer(self.settings).render(path)
        return FunctionContext.from_flat_context(
            rr.placeholder_context,
            sources=rr.placeholder_sources,
            repo_root=self.repo_root,
            manifest_path=path,
        )

    def _lock_payload(self, lock_file: Path | None) -> dict[str, Any]:
        path = lock_file or Path("bkkt/functions.lock.yaml")
        resolved = path if path.is_absolute() else self.repo_root / path
        if not resolved.exists():
            return {
                "status": "not_configured",
                "path": _relative(self.repo_root, resolved),
                "summary": {"changes": 0, "issues": 0},
                "changes": [],
                "issues": [],
            }
        try:
            return (
                FunctionLockService(self.settings)
                .check_lock(lock_path=path)
                .to_payload()
            )
        except ConnectCtlError as e:
            return {
                "status": "failed",
                "path": _relative(self.repo_root, resolved),
                "summary": {"changes": 0, "issues": 1},
                "changes": [],
                "issues": [
                    {
                        "code": "function_lock_error",
                        "severity": "error",
                        "message": str(e),
                    }
                ],
            }


class VariableReviewService:
    """Builds a single review payload for repo variable changes."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repo_root = settings.repo.root.resolve()

    def review(
        self,
        name: str,
        *,
        schema_path: str | None = None,
        override_value: Any | None = None,
        with_render_diff: bool = False,
    ) -> dict[str, Any]:
        schema = VarsSchemaLoader(self.repo_root, schema_path=schema_path).load()
        entry = next((item for item in schema.entries if item.key == name), None)
        impact = TemplateImpactService(self.settings).variable_impact(
            name,
            override_value=override_value,
            with_render_diff=with_render_diff,
        )
        schema_payload = _schema_entry_payload(
            entry,
            schema_path=schema.path,
            repo_root=self.repo_root,
        )
        impact_payload = impact.to_payload()
        checklist = _variable_checklist(
            schema_entry=entry,
            impact_payload=impact_payload,
            with_render_diff=with_render_diff,
            override_value=override_value,
        )
        status = (
            "failed" if any(item.status == "failed" for item in checklist) else "ok"
        )
        return {
            "kind": "variable_review",
            "status": status,
            "variable": name,
            "schema": schema_payload,
            "impact": impact_payload,
            "hints": _variable_hints(entry),
            "checklist": [item.to_payload() for item in checklist],
        }


def _function_checklist(
    *,
    contracts_payload: dict[str, Any],
    impact_payload: dict[str, Any],
    lock_payload: dict[str, Any],
) -> tuple[ReviewChecklistItem, ...]:
    contracts_status = str(contracts_payload.get("status"))
    contract_count = int(contracts_payload.get("summary", {}).get("total", 0) or 0)
    lock_status = str(lock_payload.get("status"))
    return (
        ReviewChecklistItem(
            code="function_registered",
            status="ok",
            message="Function is registered in TemplateRuntime.",
        ),
        ReviewChecklistItem(
            code="contract_tests",
            status=(
                "ok"
                if contracts_status == "ok" and contract_count > 0
                else "failed" if contracts_status == "failed" else "warning"
            ),
            message=(
                f"{contract_count} contract test(s) cover this function."
                if contract_count
                else "No function contract tests found; add bkkt/functions/tests coverage."
            ),
        ),
        ReviewChecklistItem(
            code="usage_impact",
            status="ok",
            message=(
                f"{impact_payload.get('summary', {}).get('matches', 0)} manifest "
                "usage(s) found."
            ),
        ),
        ReviewChecklistItem(
            code="function_lock",
            status=(
                "ok"
                if lock_status == "ok"
                else "failed" if lock_status == "failed" else "warning"
            ),
            message=(
                "Function lockfile is up to date."
                if lock_status == "ok"
                else (
                    "Function lockfile is not configured."
                    if lock_status == "not_configured"
                    else "Function lockfile has issues."
                )
            ),
        ),
    )


def _variable_checklist(
    *,
    schema_entry: VarsSchemaEntry | None,
    impact_payload: dict[str, Any],
    with_render_diff: bool,
    override_value: Any | None,
) -> tuple[ReviewChecklistItem, ...]:
    render_diff_count = int(
        impact_payload.get("summary", {}).get("render_diffs", 0) or 0
    )
    return (
        ReviewChecklistItem(
            code="schema_entry",
            status="ok" if schema_entry else "warning",
            message=(
                "Variable is declared in bkkt/vars.schema.yaml."
                if schema_entry
                else "Variable is not declared in vars schema."
            ),
        ),
        ReviewChecklistItem(
            code="usage_impact",
            status="ok",
            message=(
                f"{impact_payload.get('summary', {}).get('matches', 0)} manifest "
                "usage(s) found."
            ),
        ),
        ReviewChecklistItem(
            code="render_diff",
            status=(
                "ok" if with_render_diff and override_value is not None else "warning"
            ),
            message=(
                f"{render_diff_count} rendered config diff(s) found."
                if with_render_diff and override_value is not None
                else "Pass --with-render-diff and --set KEY=VALUE for before/after proof."
            ),
        ),
    )


def _schema_entry_payload(
    entry: VarsSchemaEntry | None,
    *,
    schema_path: Path | None,
    repo_root: Path,
) -> dict[str, Any] | None:
    if entry is None:
        return None
    return {
        "key": entry.key,
        "type": entry.type,
        "required": entry.required,
        "enum": list(entry.enum),
        "pattern": entry.pattern,
        "deprecated": entry.deprecated,
        "deprecated_since": entry.deprecated_since,
        "remove_after": entry.remove_after,
        "replacement": entry.replacement,
        "sensitive": entry.sensitive,
        "description": entry.description,
        "schema_path": _relative(repo_root, schema_path) if schema_path else None,
    }


def _variable_hints(entry: VarsSchemaEntry | None) -> list[dict[str, str]]:
    if entry is None:
        return [
            {
                "code": "missing_schema_entry",
                "message": "Add this variable to bkkt/vars.schema.yaml for self-service docs and validation.",
            }
        ]
    hints: list[dict[str, str]] = []
    if entry.sensitive:
        hints.append(
            {
                "code": "sensitive_variable",
                "message": "Treat rendered values as sensitive in screenshots and tickets.",
            }
        )
    if entry.deprecated:
        hints.append(
            {
                "code": "deprecated_variable",
                "message": "Prefer the documented replacement before adding new usages.",
            }
        )
    return hints


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)
