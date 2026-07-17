from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


TraceStepKind = Literal[
    "config_source",
    "variable",
    "function",
    "provider",
    "computed",
    "graph_edge",
]


@dataclass(frozen=True)
class TraceStep:
    kind: TraceStepKind
    name: str
    value: Any | None = None
    source: str | None = None
    detail: str | None = None
    contract: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "kind": self.kind,
            "name": self.name,
            "value": self.value,
            "source": self.source,
            "detail": self.detail,
        }
        if self.contract is not None:
            payload["contract"] = self.contract
        return payload


@dataclass(frozen=True)
class ConfigTraceReport:
    manifest: str
    config_key: str
    final_value: Any | None
    steps: tuple[TraceStep, ...]
    status: str = "ok"

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "manifest": self.manifest,
            "config_key": self.config_key,
            "final_value": self.final_value,
            "steps": [step.to_payload() for step in self.steps],
        }


@dataclass(frozen=True)
class VarTraceUsage:
    config_key: str
    kind: str
    via_function: str | None = None

    def to_payload(self) -> dict[str, str | None]:
        return {
            "config_key": self.config_key,
            "kind": self.kind,
            "via_function": self.via_function,
        }


@dataclass(frozen=True)
class VarTraceReport:
    manifest: str
    variable: str
    value: Any | None
    source: str | None
    usages: tuple[VarTraceUsage, ...]
    steps: tuple[TraceStep, ...] = ()
    status: str = "ok"

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "manifest": self.manifest,
            "variable": self.variable,
            "value": self.value,
            "source": self.source,
            "steps": [step.to_payload() for step in self.steps],
            "usages": [usage.to_payload() for usage in self.usages],
        }
