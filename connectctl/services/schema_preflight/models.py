from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]


class PreflightDecision(str, Enum):
    pass_ = "pass"
    warn = "warn"
    block = "block"


@dataclass(frozen=True)
class SchemaRisk:
    risk_id: str
    severity: str
    message: str
    changed_keys: tuple[str, ...] = ()
    allowed: bool = False
    allowlist_entry: JsonObject | None = None

    def to_payload(self) -> JsonObject:
        return {
            "risk_id": self.risk_id,
            "severity": self.severity,
            "message": self.message,
            "changed_keys": list(self.changed_keys),
            "allowed": self.allowed,
            "allowlist_entry": self.allowlist_entry,
        }


@dataclass(frozen=True)
class SchemaPreflightResult:
    connector: str
    decision: PreflightDecision
    mode: str
    risks: tuple[SchemaRisk, ...]
    exact_checks: tuple[JsonObject, ...] = ()

    @property
    def blocked(self) -> bool:
        return self.decision is PreflightDecision.block

    def to_payload(self) -> JsonObject:
        return {
            "connector": self.connector,
            "decision": self.decision.value,
            "mode": self.mode,
            "risks": [risk.to_payload() for risk in self.risks],
            "exact_checks": list(self.exact_checks),
        }


@dataclass(frozen=True)
class CandidateSchemaFile:
    subject: str
    path: Path

    def to_payload(self) -> JsonObject:
        return {"subject": self.subject, "path": str(self.path)}
