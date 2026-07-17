from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..utils import flatten_dict


@dataclass(frozen=True)
class VarsProfile:
    name: str
    description: str
    values: dict[str, Any]
    source_path: Path

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "source_path": str(self.source_path),
            "vars": self.values,
            "flat_vars": flatten_dict(self.values),
        }


@dataclass(frozen=True)
class VarsProfileChange:
    key: str
    before: Any
    after: Any
    source: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "before": self.before,
            "after": self.after,
            "source": self.source,
        }


@dataclass(frozen=True)
class VarsProfileDiff:
    profile: VarsProfile
    manifest: str
    changes: tuple[VarsProfileChange, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "profile": self.profile.name,
            "manifest": self.manifest,
            "changes": [item.to_payload() for item in self.changes],
            "summary": {"changes": len(self.changes)},
        }
