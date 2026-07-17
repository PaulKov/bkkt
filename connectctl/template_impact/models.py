from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..template_inventory import TemplateUsage


@dataclass(frozen=True, order=True)
class RenderDiff:
    manifest: str
    config_key: str
    before: Any
    after: Any

    def to_payload(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest,
            "config_key": self.config_key,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class TemplateImpactReport:
    kind: Literal["variable", "function"]
    name: str
    matches: tuple[TemplateUsage, ...]
    render_diffs: tuple[RenderDiff, ...] = ()
    metadata: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "query": {"kind": self.kind, "name": self.name},
            "summary": {
                "matches": len(self.matches),
                "render_diffs": len(self.render_diffs),
            },
            "matches": [item.to_payload() for item in self.matches],
            "render_diffs": [item.to_payload() for item in self.render_diffs],
        }
        if self.metadata:
            payload.update(self.metadata)
        return payload
