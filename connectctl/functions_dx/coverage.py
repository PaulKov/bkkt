from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ..function_contracts import FunctionContractLoader
from ..settings_models import Settings
from ..template_inventory import TemplateInventoryScanner
from ..template_runtime import TemplateRuntime
from ..template_runtime.models import FunctionDescriptor
from ..vars_contracts import VarsSchemaEntry, VarsSchemaLoader


@dataclass(frozen=True)
class CoverageGateOptions:
    """Strict coverage gate options shared by functions and vars reports."""

    strict: bool = False
    today: date | None = None

    @property
    def effective_today(self) -> date:
        return self.today or date.today()


@dataclass(frozen=True)
class FunctionCoverageService:
    """Builds repo-wide quality coverage for registered template functions."""

    settings: Settings
    gate: CoverageGateOptions = CoverageGateOptions()

    def report(self) -> dict[str, Any]:
        runtime = TemplateRuntime.from_settings(self.settings)
        inventory = TemplateInventoryScanner(self.settings).scan()
        contracts_by_function = _function_contract_counts(self.settings.repo.root)
        items = [
            _function_coverage_item(
                descriptor,
                usage_count=len(inventory.used_by_function(descriptor.name)),
                contract_count=contracts_by_function.get(descriptor.name, 0),
                today=self.gate.effective_today,
            )
            for descriptor in runtime.list_functions()
        ]
        issues = _function_issues(items, gate=self.gate)
        return {
            "kind": "function_coverage",
            "status": _overall_status(items, issues),
            "summary": {
                "functions": len(items),
                "repo_functions": sum(1 for item in items if item["source"] == "repo"),
                "used_functions": len(inventory.used_functions),
                "missing_contract_tests": sum(
                    1
                    for item in items
                    if item["source"] == "repo"
                    and item["contract_tests"]["status"] == "missing"
                ),
                "issues": len(issues),
            },
            "issues": issues,
            "items": items,
        }


@dataclass(frozen=True)
class VariableCoverageService:
    """Builds repo-wide coverage for placeholder variables and typed schema."""

    settings: Settings
    schema_path: str | None = None
    gate: CoverageGateOptions = CoverageGateOptions()

    def report(self) -> dict[str, Any]:
        inventory = TemplateInventoryScanner(self.settings).scan()
        schema = VarsSchemaLoader(
            self.settings.repo.root, schema_path=self.schema_path
        ).load()
        schema_by_key = {entry.key: entry for entry in schema.entries}
        all_keys = sorted(set(schema_by_key) | inventory.used_variables)
        items = [
            _variable_coverage_item(
                key,
                usage_count=len(inventory.used_by_variable(key)),
                schema_entry=schema_by_key.get(key),
                today=self.gate.effective_today,
            )
            for key in all_keys
        ]
        issues = _variable_issues(items, gate=self.gate)
        return {
            "kind": "variable_coverage",
            "status": _overall_status(items, issues),
            "schema_path": str(schema.path) if schema.path else None,
            "summary": {
                "variables": len(items),
                "schema_entries": len(schema.entries),
                "used_variables": len(inventory.used_variables),
                "missing_schema_entries": sum(
                    1 for item in items if item["schema_entry"]["status"] == "missing"
                ),
                "issues": len(issues),
            },
            "issues": issues,
            "items": items,
        }


def _function_contract_counts(repo_root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in FunctionContractLoader(repo_root).load():
        counts[case.function] = counts.get(case.function, 0) + 1
    return counts


def _function_coverage_item(
    descriptor: FunctionDescriptor,
    *,
    usage_count: int,
    contract_count: int,
    today: date,
) -> dict[str, Any]:
    contract_status = "ok" if contract_count else "missing"
    lifecycle = descriptor.lifecycle_payload()
    status = (
        "warning"
        if descriptor.source == "repo" and contract_status == "missing"
        else "ok"
    )
    if lifecycle.get("deprecated"):
        status = "warning"
    if _is_expired(lifecycle.get("remove_after"), today):
        status = "failed"
    return {
        "name": descriptor.name,
        "description": descriptor.description.strip(),
        "source": descriptor.source,
        "source_path": str(descriptor.source_path) if descriptor.source_path else None,
        "package": descriptor.package,
        "usage_count": usage_count,
        "contract_tests": {
            "status": contract_status,
            "total": contract_count,
        },
        "lifecycle": lifecycle,
        "status": status,
    }


def _variable_coverage_item(
    key: str,
    *,
    usage_count: int,
    schema_entry: VarsSchemaEntry | None,
    today: date,
) -> dict[str, Any]:
    if schema_entry is None:
        schema_payload = {
            "status": "missing",
            "type": None,
            "required": False,
            "sensitive": False,
            "deprecated": False,
            "replacement": None,
            "remove_after": None,
            "description": "",
        }
        status = "warning"
    else:
        schema_payload = {
            "status": "ok",
            "type": schema_entry.type,
            "required": schema_entry.required,
            "sensitive": schema_entry.sensitive,
            "deprecated": schema_entry.deprecated,
            "replacement": schema_entry.replacement,
            "remove_after": schema_entry.remove_after,
            "description": schema_entry.description,
        }
        status = "warning" if schema_entry.deprecated else "ok"
        if _is_expired(schema_entry.remove_after, today):
            status = "failed"
    return {
        "key": key,
        "usage_count": usage_count,
        "schema_entry": schema_payload,
        "status": status,
    }


def _function_issues(
    items: list[dict[str, Any]], *, gate: CoverageGateOptions
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item in items:
        if item["source"] == "repo" and item["contract_tests"]["status"] == "missing":
            issues.append(
                _issue(
                    code="missing_function_contract",
                    strict=gate.strict,
                    name=item["name"],
                    message=(
                        f"Repo-local function {item['name']!r} has no contract tests."
                    ),
                )
            )
        lifecycle = item.get("lifecycle", {})
        if _is_expired(lifecycle.get("remove_after"), gate.effective_today):
            item["status"] = "failed"
            issues.append(
                _issue(
                    code="expired_function_deprecation",
                    strict=True,
                    name=item["name"],
                    message=(
                        f"Function {item['name']!r} passed remove_after="
                        f"{lifecycle.get('remove_after')}."
                    ),
                )
            )
    return issues


def _variable_issues(
    items: list[dict[str, Any]], *, gate: CoverageGateOptions
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item in items:
        schema = item["schema_entry"]
        if schema["status"] == "missing":
            issues.append(
                _issue(
                    code="missing_variable_schema_entry",
                    strict=gate.strict,
                    key=item["key"],
                    message=(
                        f"Variable {item['key']!r} is used but missing from "
                        "bkkt/vars.schema.yaml."
                    ),
                )
            )
        if _is_expired(schema.get("remove_after"), gate.effective_today):
            item["status"] = "failed"
            issues.append(
                _issue(
                    code="expired_variable_deprecation",
                    strict=True,
                    key=item["key"],
                    message=(
                        f"Variable {item['key']!r} passed remove_after="
                        f"{schema.get('remove_after')}."
                    ),
                )
            )
    return issues


def _issue(
    *,
    code: str,
    strict: bool,
    message: str,
    name: str | None = None,
    key: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "error" if strict else "warning",
        "name": name,
        "key": key,
        "message": message,
    }


def _is_expired(remove_after: Any, today: date) -> bool:
    if not remove_after:
        return False
    try:
        return date.fromisoformat(str(remove_after)) < today
    except ValueError:
        return False


def _overall_status(items: list[dict[str, Any]], issues: list[dict[str, Any]]) -> str:
    if any(issue.get("severity") == "error" for issue in issues):
        return "failed"
    if any(item.get("status") == "failed" for item in items):
        return "failed"
    if any(item.get("status") == "warning" for item in items):
        return "warning"
    return "ok"
