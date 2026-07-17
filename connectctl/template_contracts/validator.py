from __future__ import annotations

from datetime import date
from fnmatch import fnmatch
import re
from pathlib import Path
from typing import Any, Literal, Mapping

from ..utils import flatten_dict
from .models import (
    TemplateContract,
    TemplateContractInput,
    TemplateContractIssue,
    TemplateContractValidation,
    TemplateContractValidationResult,
)


class TemplateContractValidator:
    """Validates one manifest context against applicable template contracts."""

    def __init__(self, *, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()

    def validate(
        self,
        *,
        manifest_path: Path,
        contracts: tuple[TemplateContract, ...],
        values: Mapping[str, Any],
        sources: Mapping[str, str] | None = None,
    ) -> TemplateContractValidationResult:
        rel_manifest = _relative(self.repo_root, manifest_path)
        applicable = tuple(
            contract
            for contract in contracts
            if _matches_manifest(rel_manifest, contract.manifests)
        )
        source_map = sources or {}
        validations = tuple(
            TemplateContractValidation(
                contract=contract,
                issues=tuple(
                    issue
                    for item in contract.inputs
                    for issue in _validate_input(item, values, source_map)
                ),
            )
            for contract in applicable
        )
        return TemplateContractValidationResult(
            manifest=rel_manifest,
            contracts=validations,
        )


def _validate_input(
    item: TemplateContractInput,
    values: Mapping[str, Any],
    sources: Mapping[str, str],
) -> list[TemplateContractIssue]:
    issues: list[TemplateContractIssue] = []
    present = item.key in values
    value = values.get(item.key, item.default)
    if not present and item.default is None:
        if item.required:
            issues.append(
                TemplateContractIssue(
                    code="required_missing",
                    key=item.key,
                    message=f"Required template input {item.key!r} is missing",
                    expected="present",
                    actual=None,
                )
            )
        return issues

    issues.extend(_lifecycle_issues(item, value, sources))
    if not _matches_type(value, item.type):
        issues.append(
            TemplateContractIssue(
                code="type_mismatch",
                key=item.key,
                message=(
                    f"Template input {item.key!r} must be {item.type}, "
                    f"got {type(value).__name__}"
                ),
                expected=item.type,
                actual=value,
                source=sources.get(item.key),
            )
        )
    if item.enum and value not in item.enum:
        issues.append(
            TemplateContractIssue(
                code="enum_mismatch",
                key=item.key,
                message=f"Template input {item.key!r} must be one of {list(item.enum)!r}",
                expected=list(item.enum),
                actual=value,
                source=sources.get(item.key),
            )
        )
    if item.pattern and not re.search(item.pattern, str(value)):
        issues.append(
            TemplateContractIssue(
                code="pattern_mismatch",
                key=item.key,
                message=f"Template input {item.key!r} must match regex {item.pattern!r}",
                expected=item.pattern,
                actual=value,
                source=sources.get(item.key),
            )
        )
    return issues


def _lifecycle_issues(
    item: TemplateContractInput,
    value: Any,
    sources: Mapping[str, str],
) -> list[TemplateContractIssue]:
    if not item.deprecated:
        return []
    severity: Literal["error", "warning"] = (
        "error" if _is_expired(item.remove_after) else "warning"
    )
    remove_hint = (
        f" and must be removed after {item.remove_after}" if item.remove_after else ""
    )
    return [
        TemplateContractIssue(
            code="deprecated",
            key=item.key,
            message=f"Template input {item.key!r} is deprecated{remove_hint}",
            severity=severity,
            actual=value,
            source=sources.get(item.key),
            replacement=item.replacement,
        )
    ]


def context_from_manifest_vars(
    raw: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    vars_raw = raw.get("vars", {}) or {}
    values = flatten_dict(vars_raw) if isinstance(vars_raw, Mapping) else {}
    return values, {key: "manifest:vars" for key in values}


def _matches_manifest(rel_manifest: str, patterns: tuple[str, ...]) -> bool:
    if not patterns:
        return True
    return any(fnmatch(rel_manifest, pattern) for pattern in patterns)


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)


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
