from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ..vars_contracts import VarsSchemaEntry


@dataclass(frozen=True)
class ProviderContract:
    provider: str
    provides: tuple[VarsSchemaEntry, ...]
    capabilities: tuple[str, ...] = ()
    source_path: Path | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "source_path": str(self.source_path) if self.source_path else None,
            "capabilities": list(self.capabilities),
            "provides": {
                item.key: {
                    "type": item.type,
                    "required": item.required,
                    "pattern": item.pattern,
                    "enum": list(item.enum),
                    "sensitive": item.sensitive,
                    "description": item.description,
                }
                for item in self.provides
            },
        }


@dataclass(frozen=True)
class ProviderContractSuite:
    contracts: tuple[ProviderContract, ...]

    def get(self, provider: str) -> ProviderContract | None:
        for contract in self.contracts:
            if contract.provider == provider:
                return contract
        return None

    def to_schema_payload(self) -> dict[str, Any]:
        return {
            "version": 1,
            "providers": {
                contract.provider: {
                    "capabilities": list(contract.capabilities),
                    "provides": {
                        entry.key: {
                            "type": entry.type,
                            "required": entry.required,
                            "pattern": entry.pattern,
                            "enum": list(entry.enum),
                            "sensitive": entry.sensitive,
                            "description": entry.description,
                        }
                        for entry in contract.provides
                    },
                }
                for contract in self.contracts
            },
        }


@dataclass(frozen=True)
class VarPreflightIssue:
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"
    provider: str | None = None
    key: str | None = None
    expected: Any | None = None
    actual: Any | None = None
    source: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "provider": self.provider,
            "key": self.key,
            "expected": self.expected,
            "actual": self.actual,
            "source": self.source,
        }


@dataclass(frozen=True)
class ProviderContractResult:
    provider: str
    status: Literal["ok", "failed"]
    values: dict[str, Any]
    issues: tuple[VarPreflightIssue, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "values": dict(sorted(self.values.items())),
            "issues": [issue.to_payload() for issue in self.issues],
        }


@dataclass(frozen=True)
class SecretReference:
    provider: str
    secret: str
    field: str
    config_key: str

    def to_payload(self, *, status: str) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "secret": self.secret,
            "field": self.field,
            "config_key": self.config_key,
            "status": status,
        }


@dataclass(frozen=True)
class SecretReferenceCheckResult:
    refs: tuple[dict[str, Any], ...]
    issues: tuple[VarPreflightIssue, ...]


@dataclass(frozen=True)
class VarPreflightResult:
    manifest: str
    provider_contracts: tuple[ProviderContractResult, ...]
    secret_refs: tuple[dict[str, Any], ...]
    issues: tuple[VarPreflightIssue, ...]

    @property
    def status(self) -> str:
        return (
            "failed"
            if any(issue.severity == "error" for issue in self.issues)
            else "ok"
        )

    @property
    def exit_code(self) -> int:
        return 1 if self.status == "failed" else 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "manifest": self.manifest,
            "summary": {
                "issues": len(self.issues),
                "provider_contracts": len(self.provider_contracts),
                "secret_refs": len(self.secret_refs),
            },
            "provider_contracts": [
                result.to_payload() for result in self.provider_contracts
            ],
            "secret_refs": list(self.secret_refs),
            "issues": [issue.to_payload() for issue in self.issues],
        }
