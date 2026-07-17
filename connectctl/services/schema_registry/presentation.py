from __future__ import annotations

from typing import Any


class SchemaScope:
    def __init__(
        self,
        *,
        env: Any,
        cluster: Any,
        schema_registry: Any,
        schema_registry_source: str = "cluster config",
    ) -> None:
        self.env = env
        self.cluster = cluster
        self.schema_registry = schema_registry
        self.schema_registry_source = schema_registry_source

    def payload(self) -> dict[str, Any]:
        return {
            "env": self.env.value,
            "cluster_group": self.cluster.name,
            "schema_registry_urls": list(self.schema_registry.urls),
            "schema_registry_source": self.schema_registry_source,
        }


def subjects_text(scope: SchemaScope, subjects: list[str]) -> str:
    lines = [_heading(scope, "Schema Registry subjects"), "| Subject |", "|---|"]
    lines.extend(f"| `{subject}` |" for subject in subjects)
    return "\n".join(lines) + "\n"


def versions_text(scope: SchemaScope, *, subject: str, versions: list[int]) -> str:
    return (
        _heading(scope, f"Schema subject `{subject}` versions")
        + "\n".join(f"- `{version}`" for version in versions)
        + "\n"
    )


def subject_describe_text(scope: SchemaScope, desc: Any) -> str:
    latest = desc.latest
    lines = [_heading(scope, f"Schema subject `{desc.subject}`")]
    lines.append(f"- versions: `{', '.join(str(x) for x in desc.versions) or '-'}`")
    if latest:
        lines.append(f"- latest_version: `{latest.version}`")
        lines.append(f"- latest_id: `{latest.schema_id}`")
        lines.append(f"- schema_type: `{latest.schema_type}`")
    return "\n".join(lines) + "\n"


def version_text(scope: SchemaScope, version: Any) -> str:
    lines = [
        _heading(
            scope, f"Schema subject `{version.subject}` version `{version.version}`"
        )
    ]
    lines.append(f"- id: `{version.schema_id}`")
    lines.append(f"- schema_type: `{version.schema_type}`")
    if version.references:
        lines.append(f"- references: `{len(version.references)}`")
    lines.append("\n```json")
    lines.append(version.schema)
    lines.append("```")
    return "\n".join(lines) + "\n"


def diff_text(scope: SchemaScope, diff: Any) -> str:
    lines = [_heading(scope, f"Schema diff `{diff.subject}`")]
    lines.append(f"- from_version: `{diff.from_version}`")
    lines.append(f"- to_version: `{diff.to_version}`")
    lines.append("\n```diff")
    lines.extend(diff.unified_diff or ("# no schema diff",))
    lines.append("```")
    return "\n".join(lines) + "\n"


def compat_text(scope: SchemaScope, subject: str | None, level: str) -> str:
    target = f"subject `{subject}`" if subject else "global registry"
    return (
        _heading(scope, f"Compatibility for {target}") + f"- compatibility: `{level}`\n"
    )


def compat_set_text(scope: SchemaScope, payload: dict[str, Any]) -> str:
    subject = payload.get("subject") or "<global>"
    lines = [_heading(scope, f"Compatibility set `{subject}`")]
    lines.append(f"- dry_run: `{str(payload.get('dry_run')).lower()}`")
    lines.append(f"- applied: `{str(payload.get('applied')).lower()}`")
    lines.append(f"- current: `{payload.get('current_compatibility')}`")
    lines.append(f"- desired: `{payload.get('desired_compatibility')}`")
    if not payload.get("applied"):
        lines.append("- next: rerun with `--yes` after reviewing this plan")
    return "\n".join(lines) + "\n"


def check_text(scope: SchemaScope, check: Any) -> str:
    lines = [_heading(scope, f"Compatibility check `{check.subject}`")]
    lines.append(f"- version: `{check.version}`")
    lines.append(f"- compatible: `{str(check.compatible).lower()}`")
    if check.messages:
        lines.append("- messages:")
        lines.extend(f"  - {msg}" for msg in check.messages)
    return "\n".join(lines) + "\n"


def plan_text(scope: SchemaScope, payload: dict[str, Any]) -> str:
    lines = [_heading(scope, f"Schema evolution plan `{payload.get('subject')}`")]
    lines.append(f"- schema_file: `{payload.get('schema_file')}`")
    lines.append(f"- schema_type: `{payload.get('candidate', {}).get('schema_type')}`")
    compatibility = payload.get("compatibility") or {}
    lines.append(f"- compatible: `{str(compatibility.get('compatible')).lower()}`")
    lines.append(
        f"- safe_to_register: `{str(payload.get('safe_to_register')).lower()}`"
    )
    current = payload.get("current_latest")
    if current:
        lines.append(f"- current_latest_version: `{current.get('version')}`")
        lines.append(f"- current_latest_id: `{current.get('id')}`")
    elif payload.get("current_latest_error"):
        lines.append(f"- current_latest_error: `{payload.get('current_latest_error')}`")
    warnings = list(payload.get("warnings") or [])
    if warnings:
        lines.append("\n## Warnings")
        lines.extend(f"- {warning}" for warning in warnings)
    next_commands = list(payload.get("next_commands") or [])
    if next_commands:
        lines.append("\n## Next Commands")
        lines.extend(f"- `{cmd}`" for cmd in next_commands)
    return "\n".join(lines) + "\n"


def register_text(scope: SchemaScope, payload: dict[str, Any]) -> str:
    lines = [_heading(scope, f"Schema register `{payload.get('subject')}`")]
    lines.append(f"- dry_run: `{str(payload.get('dry_run')).lower()}`")
    lines.append(f"- applied: `{str(payload.get('applied')).lower()}`")
    lines.append(f"- schema_file: `{payload.get('schema_file')}`")
    lines.append(
        f"- compatible: `{str((payload.get('compatibility') or {}).get('compatible')).lower()}`"
    )
    if payload.get("warnings"):
        lines.append("\n## Warnings")
        lines.extend(f"- {warning}" for warning in payload.get("warnings") or [])
    result = payload.get("result")
    if result:
        lines.append("\n## Registered")
        lines.append(f"- id: `{result.get('id')}`")
        lines.append(f"- version: `{result.get('version') or '-'}`")
    elif not payload.get("applied"):
        lines.append("- next: rerun with `--yes` after reviewing the plan")
    return "\n".join(lines) + "\n"


def impact_text(scope: SchemaScope, impact: Any) -> str:
    lines = [_heading(scope, f"Schema impact `{impact.subject}`")]
    lines.append(f"- inferred_topic: `{impact.topic or '-'}`")
    lines.append(f"- key_or_value: `{impact.key_or_value or '-'}`")
    if impact.suggested_commands:
        lines.append("\n## Suggested next commands")
        lines.extend(f"- `{cmd}`" for cmd in impact.suggested_commands)
    if impact.notes:
        lines.append("\n## Notes")
        lines.extend(f"- {note}" for note in impact.notes)
    return "\n".join(lines) + "\n"


def _heading(scope: SchemaScope, title: str) -> str:
    return (
        f"# {title}\n\n"
        f"- env: `{scope.env.value}`\n"
        f"- cluster_group: `{scope.cluster.name}`\n"
        f"- schema_registry_urls: `{', '.join(scope.schema_registry.urls)}`\n"
    )
