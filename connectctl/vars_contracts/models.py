from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


VarType = Literal["string", "int", "float", "bool", "number", "any"]


@dataclass(frozen=True)
class VarsSchemaEntry:
    key: str
    type: VarType = "any"
    required: bool = False
    enum: tuple[Any, ...] = ()
    pattern: str | None = None
    deprecated: bool = False
    deprecated_since: str | None = None
    remove_after: str | None = None
    replacement: str | None = None
    sensitive: bool = False
    description: str = ""


@dataclass(frozen=True)
class VarsSchema:
    path: Path | None
    entries: tuple[VarsSchemaEntry, ...]

    @property
    def is_present(self) -> bool:
        return self.path is not None


@dataclass(frozen=True)
class VarsSchemaIssue:
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
class VarsDoctorResult:
    schema: VarsSchema
    issues: tuple[VarsSchemaIssue, ...]

    @property
    def status(self) -> str:
        return "failed" if any(i.severity == "error" for i in self.issues) else "ok"

    @property
    def exit_code(self) -> int:
        return 1 if self.status == "failed" else 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "schema_path": str(self.schema.path) if self.schema.path else None,
            "issues": [issue.to_payload() for issue in self.issues],
            "summary": {
                "total": len(self.issues),
                "errors": sum(1 for i in self.issues if i.severity == "error"),
                "warnings": sum(1 for i in self.issues if i.severity == "warning"),
            },
        }
