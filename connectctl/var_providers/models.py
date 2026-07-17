from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class VarProviderDescriptor:
    name: str
    fn: Callable[..., Any]
    description: str
    source_path: Path | None = None
    provides: tuple[str, ...] = ()
    allow_shadow: bool = False
    capabilities: tuple[str, ...] = ()
    timeout_ms: int | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description.strip(),
            "source": "repo",
            "source_path": str(self.source_path) if self.source_path else None,
            "provides": list(self.provides),
            "allow_shadow": self.allow_shadow,
            "capabilities": list(self.capabilities),
            "timeout_ms": self.timeout_ms,
        }


@dataclass(frozen=True)
class VarProviderValue:
    key: str
    value: str | int | float | bool
    source: str

    def to_payload(self) -> dict[str, Any]:
        return {"key": self.key, "value": self.value, "source": self.source}


@dataclass(frozen=True)
class VarProviderRunResult:
    provider: VarProviderDescriptor
    values: tuple[VarProviderValue, ...]

    @property
    def source(self) -> str:
        return f"provider:{self.provider.name}"

    def to_payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider.to_payload(),
            "source": self.source,
            "values": {item.key: item.value for item in self.values},
        }
