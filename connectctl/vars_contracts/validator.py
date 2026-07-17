from __future__ import annotations

from datetime import date
import re
from typing import Any, Literal, Mapping

from .models import VarsDoctorResult, VarsSchema, VarsSchemaEntry, VarsSchemaIssue


class VarsSchemaValidator:
    """Validates rendered placeholder context against typed vars schema."""

    def validate(
        self,
        schema: VarsSchema,
        values: Mapping[str, Any],
        *,
        sources: Mapping[str, str] | None = None,
    ) -> VarsDoctorResult:
        issues: list[VarsSchemaIssue] = []
        source_map = sources or {}
        for entry in schema.entries:
            if entry.key not in values:
                if entry.required:
                    issues.append(
                        VarsSchemaIssue(
                            code="required_missing",
                            key=entry.key,
                            message=f"Required variable {entry.key!r} is missing",
                            expected="present",
                            actual=None,
                        )
                    )
                continue
            value = values[entry.key]
            issues.extend(self._validate_present(entry, value, source_map))
        return VarsDoctorResult(schema=schema, issues=tuple(issues))

    def _validate_present(
        self,
        entry: VarsSchemaEntry,
        value: Any,
        sources: Mapping[str, str],
    ) -> list[VarsSchemaIssue]:
        issues: list[VarsSchemaIssue] = []
        if entry.deprecated:
            issues.append(
                VarsSchemaIssue(
                    code="deprecated",
                    key=entry.key,
                    message=f"Variable {entry.key!r} is deprecated",
                    severity="error",
                    actual=value,
                    source=sources.get(entry.key),
                    replacement=entry.replacement,
                )
            )
        elif entry.deprecated_since or entry.remove_after or entry.replacement:
            severity: Literal["error", "warning"] = (
                "error" if _is_expired(entry.remove_after) else "warning"
            )
            remove_hint = (
                f" and must be removed after {entry.remove_after}"
                if entry.remove_after
                else ""
            )
            issues.append(
                VarsSchemaIssue(
                    code="deprecated",
                    key=entry.key,
                    message=f"Variable {entry.key!r} is deprecated{remove_hint}",
                    severity=severity,
                    actual=value,
                    source=sources.get(entry.key),
                    replacement=entry.replacement,
                )
            )
        if not _matches_type(value, entry.type):
            issues.append(
                VarsSchemaIssue(
                    code="type_mismatch",
                    key=entry.key,
                    message=(
                        f"Variable {entry.key!r} must be {entry.type}, "
                        f"got {type(value).__name__}"
                    ),
                    expected=entry.type,
                    actual=value,
                    source=sources.get(entry.key),
                )
            )
        if entry.enum and value not in entry.enum:
            issues.append(
                VarsSchemaIssue(
                    code="enum_mismatch",
                    key=entry.key,
                    message=f"Variable {entry.key!r} must be one of {list(entry.enum)!r}",
                    expected=list(entry.enum),
                    actual=value,
                    source=sources.get(entry.key),
                )
            )
        if entry.pattern and not re.search(entry.pattern, str(value)):
            issues.append(
                VarsSchemaIssue(
                    code="pattern_mismatch",
                    key=entry.key,
                    message=(
                        f"Variable {entry.key!r} must match regex {entry.pattern!r}"
                    ),
                    expected=entry.pattern,
                    actual=value,
                    source=sources.get(entry.key),
                )
            )
        return issues


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "any":
        return True
    if expected == "string":
        return isinstance(value, str)
    if expected == "bool":
        return isinstance(value, bool)
    if expected == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "float":
        return isinstance(value, float) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False


def _is_expired(remove_after: str | None) -> bool:
    if not remove_after:
        return False
    try:
        return date.today() >= date.fromisoformat(remove_after)
    except ValueError:
        return False
