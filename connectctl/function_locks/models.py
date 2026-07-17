from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


FunctionLockStatus = Literal["ok", "failed"]
FunctionLockChangeKind = Literal[
    "added",
    "removed",
    "changed",
]


@dataclass(frozen=True, order=True)
class LockedFunction:
    name: str
    package: str
    source: str
    source_path: str | None
    fingerprint: str
    description: str
    capabilities: tuple[str, ...]
    lifecycle: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "package": self.package,
            "source": self.source,
            "source_path": self.source_path,
            "fingerprint": self.fingerprint,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "lifecycle": self.lifecycle,
        }


@dataclass(frozen=True, order=True)
class LockedPackage:
    name: str
    functions: tuple[LockedFunction, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "functions": [item.to_payload() for item in self.functions],
        }


@dataclass(frozen=True)
class FunctionLockDocument:
    version: int
    packages: tuple[LockedPackage, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "packages": [item.to_payload() for item in self.packages],
        }

    @property
    def functions_by_name(self) -> dict[str, LockedFunction]:
        return {
            function.name: function
            for package in self.packages
            for function in package.functions
        }


@dataclass(frozen=True, order=True)
class FunctionLockChange:
    kind: FunctionLockChangeKind
    function: str
    package: str
    before_fingerprint: str | None = None
    after_fingerprint: str | None = None
    before_source_path: str | None = None
    after_source_path: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "function": self.function,
            "package": self.package,
            "before_fingerprint": self.before_fingerprint,
            "after_fingerprint": self.after_fingerprint,
            "before_source_path": self.before_source_path,
            "after_source_path": self.after_source_path,
        }


@dataclass(frozen=True, order=True)
class FunctionLockIssue:
    code: str
    message: str
    function: str | None = None
    manifest: str | None = None
    config_key: str | None = None
    severity: str = "error"

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "function": self.function,
            "manifest": self.manifest,
            "config_key": self.config_key,
        }


@dataclass(frozen=True)
class FunctionLockCheckResult:
    status: FunctionLockStatus
    changes: tuple[FunctionLockChange, ...] = ()
    issues: tuple[FunctionLockIssue, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "changes": [item.to_payload() for item in self.changes],
            "issues": [item.to_payload() for item in self.issues],
            "summary": {
                "changes": len(self.changes),
                "issues": len(self.issues),
            },
        }
