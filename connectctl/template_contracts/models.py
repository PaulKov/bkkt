from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


InputType = Literal["string", "int", "float", "bool", "number", "any"]


@dataclass(frozen=True)
class TemplateContractInput:
    key: str
    type: InputType = "any"
    required: bool = False
    enum: tuple[Any, ...] = ()
    pattern: str | None = None
    default: Any | None = None
    deprecated_since: str | None = None
    remove_after: str | None = None
    replacement: str | None = None
    description: str = ""

    @property
    def deprecated(self) -> bool:
        return bool(self.deprecated_since or self.remove_after or self.replacement)

    def to_payload(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "type": self.type,
            "required": self.required,
            "enum": list(self.enum),
            "pattern": self.pattern,
            "default": self.default,
            "deprecated_since": self.deprecated_since,
            "remove_after": self.remove_after,
            "replacement": self.replacement,
            "description": self.description,
        }


@dataclass(frozen=True)
class TemplateContract:
    name: str
    manifests: tuple[str, ...]
    inputs: tuple[TemplateContractInput, ...]
    source_path: Path | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "manifests": list(self.manifests),
            "inputs": [item.to_payload() for item in self.inputs],
            "source_path": str(self.source_path) if self.source_path else None,
        }


@dataclass(frozen=True)
class TemplateContractIssue:
    code: str
    key: str
    message: str
    severity: Literal["error", "warning"] = "error"
    expected: Any | None = None
    actual: Any | None = None
    source: str | None = None
    replacement: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "key": self.key,
            "message": self.message,
            "severity": self.severity,
            "expected": self.expected,
            "actual": self.actual,
            "source": self.source,
            "replacement": self.replacement,
        }


@dataclass(frozen=True)
class TemplateContractValidation:
    contract: TemplateContract
    issues: tuple[TemplateContractIssue, ...]

    @property
    def errors(self) -> int:
        return sum(1 for item in self.issues if item.severity == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for item in self.issues if item.severity == "warning")

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.contract.name,
            "source_path": (
                str(self.contract.source_path) if self.contract.source_path else None
            ),
            "issues": [item.to_payload() for item in self.issues],
            "summary": {"errors": self.errors, "warnings": self.warnings},
        }


@dataclass(frozen=True)
class TemplateContractValidationResult:
    manifest: str
    contracts: tuple[TemplateContractValidation, ...]

    @property
    def errors(self) -> int:
        return sum(item.errors for item in self.contracts)

    @property
    def warnings(self) -> int:
        return sum(item.warnings for item in self.contracts)

    @property
    def status(self) -> str:
        return "failed" if self.errors else "ok"

    @property
    def exit_code(self) -> int:
        return 1 if self.errors else 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "manifest": self.manifest,
            "summary": {
                "contracts": len(self.contracts),
                "errors": self.errors,
                "warnings": self.warnings,
            },
            "contracts": [item.to_payload() for item in self.contracts],
        }
