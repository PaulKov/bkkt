from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ..exceptions import ConnectCtlError
from ..settings_models import Settings
from ..template_inventory import TemplateInventoryScanner
from ..template_runtime import TemplateRuntime
from ..vars_contracts import VarsSchemaEntry, VarsSchemaLoader


RefactorKind = Literal[
    "function_rename_plan",
    "variable_rename_plan",
    "function_deprecate_plan",
    "variable_deprecate_plan",
]


@dataclass(frozen=True)
class FunctionRefactorPlanner:
    """Plans safe repo-local function lifecycle changes without rewriting files."""

    settings: Settings

    def rename(self, old_name: str, new_name: str, *, dry_run: bool) -> dict[str, Any]:
        _require_dry_run(dry_run)
        inventory = TemplateInventoryScanner(self.settings).scan()
        changes = [
            {
                "path": usage.manifest,
                "config_key": usage.config_key,
                "kind": usage.kind,
                "before": old_name,
                "after": new_name,
            }
            for usage in inventory.used_by_function(old_name)
        ]
        return _rename_payload(
            "function_rename_plan",
            old_name,
            new_name,
            changes,
        )

    def deprecate(
        self,
        name: str,
        *,
        replacement: str | None,
        remove_after: str | None,
        dry_run: bool,
    ) -> dict[str, Any]:
        _require_dry_run(dry_run)
        runtime = TemplateRuntime.from_settings(self.settings)
        descriptor = runtime.registry.get(name)
        inventory = TemplateInventoryScanner(self.settings).scan()
        return {
            "kind": "function_deprecate_plan",
            "status": "planned",
            "function": descriptor.to_payload(),
            "lifecycle": {
                "deprecated": True,
                "replacement": replacement,
                "remove_after": remove_after,
            },
            "summary": {
                "affected_manifests": _affected_manifest_count(
                    inventory.used_by_function(name)
                ),
                "usages": len(inventory.used_by_function(name)),
            },
            "changes": [
                {
                    "path": usage.manifest,
                    "config_key": usage.config_key,
                    "kind": usage.kind,
                    "before": name,
                    "after": name,
                }
                for usage in inventory.used_by_function(name)
            ],
        }


@dataclass(frozen=True)
class VariableRefactorPlanner:
    """Plans safe variable lifecycle changes without broad manifest rewrites."""

    settings: Settings
    schema_path: str | None = None

    def rename(self, old_key: str, new_key: str, *, dry_run: bool) -> dict[str, Any]:
        _require_dry_run(dry_run)
        inventory = TemplateInventoryScanner(self.settings).scan()
        changes = [
            {
                "path": usage.manifest,
                "config_key": usage.config_key,
                "kind": usage.kind,
                "via_function": usage.via_function,
                "before": old_key,
                "after": new_key,
            }
            for usage in inventory.used_by_variable(old_key)
        ]
        return _rename_payload(
            "variable_rename_plan",
            old_key,
            new_key,
            changes,
        )

    def deprecate(
        self,
        key: str,
        *,
        replacement: str | None,
        remove_after: str | None,
        dry_run: bool,
    ) -> dict[str, Any]:
        _require_dry_run(dry_run)
        inventory = TemplateInventoryScanner(self.settings).scan()
        schema_entry = _schema_entry(self.settings.repo.root, key, self.schema_path)
        return {
            "kind": "variable_deprecate_plan",
            "status": "planned",
            "variable": {
                "key": key,
                "schema_entry": _schema_entry_payload(schema_entry),
            },
            "lifecycle": {
                "deprecated": True,
                "replacement": replacement,
                "remove_after": remove_after,
            },
            "summary": {
                "affected_manifests": _affected_manifest_count(
                    inventory.used_by_variable(key)
                ),
                "usages": len(inventory.used_by_variable(key)),
            },
            "changes": [
                {
                    "path": usage.manifest,
                    "config_key": usage.config_key,
                    "kind": usage.kind,
                    "via_function": usage.via_function,
                    "before": key,
                    "after": key,
                }
                for usage in inventory.used_by_variable(key)
            ],
        }


def _rename_payload(
    kind: RefactorKind,
    old_value: str,
    new_value: str,
    changes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "kind": kind,
        "status": "planned",
        "from": old_value,
        "to": new_value,
        "summary": {
            "affected_manifests": _affected_manifest_count(changes),
            "usages": len(changes),
        },
        "changes": changes,
    }


def _affected_manifest_count(changes_or_usages: Any) -> int:
    manifests = {
        item["path"] if isinstance(item, dict) else item.manifest
        for item in changes_or_usages
    }
    return len(manifests)


def _schema_entry(
    repo_root: Path, key: str, schema_path: str | None
) -> VarsSchemaEntry | None:
    schema = VarsSchemaLoader(repo_root, schema_path=schema_path).load()
    return next((entry for entry in schema.entries if entry.key == key), None)


def _schema_entry_payload(entry: VarsSchemaEntry | None) -> dict[str, Any]:
    if entry is None:
        return {"status": "missing"}
    return {
        "status": "ok",
        "type": entry.type,
        "required": entry.required,
        "sensitive": entry.sensitive,
        "deprecated": entry.deprecated,
        "replacement": entry.replacement,
        "remove_after": entry.remove_after,
        "description": entry.description,
    }


def _require_dry_run(dry_run: bool) -> None:
    if dry_run:
        return
    raise ConnectCtlError(
        "This lifecycle workflow is plan-only in v1. "
        "Run with --dry-run to get a safe reviewable plan."
    )
