from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal


FunctionSource = Literal["builtin", "repo"]


@dataclass(frozen=True)
class FunctionDescriptor:
    name: str
    fn: Callable[..., Any]
    description: str
    source: FunctionSource
    source_path: Path | None = None
    deprecated_since: str | None = None
    remove_after: str | None = None
    replacement: str | None = None
    capabilities: tuple[str, ...] = ()
    timeout_ms: int | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description.strip(),
            "source": self.source,
            "source_path": str(self.source_path) if self.source_path else None,
            "lifecycle": self.lifecycle_payload(),
            "namespace": self.namespace,
            "package": self.package,
            "capabilities": list(self.capabilities),
            "timeout_ms": self.timeout_ms,
        }

    def lifecycle_payload(self) -> dict[str, Any]:
        deprecated = bool(
            self.deprecated_since or self.remove_after or self.replacement
        )
        return {
            "deprecated": deprecated,
            "deprecated_since": self.deprecated_since,
            "remove_after": self.remove_after,
            "replacement": self.replacement,
        }

    @property
    def namespace(self) -> str | None:
        return self.name.rsplit(".", 1)[0] if "." in self.name else None

    @property
    def package(self) -> str:
        return self.name.split(".", 1)[0] if "." in self.name else "default"
