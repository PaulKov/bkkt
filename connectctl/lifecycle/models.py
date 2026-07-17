from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class ConnectorLifecycle:
    """Effective lifecycle state derived from all manifest layers."""

    disabled: bool = False
    reason: Optional[str] = None
    ticket: Optional[str] = None
    until: Optional[str] = None
    disabled_sources: Tuple[str, ...] = ()

    @property
    def enabled(self) -> bool:
        return not self.disabled

    @property
    def status(self) -> str:
        return "disabled" if self.disabled else "enabled"

    def to_meta(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"disabled": self.disabled}
        if self.reason:
            payload["reason"] = self.reason
        if self.ticket:
            payload["ticket"] = self.ticket
        if self.until:
            payload["until"] = self.until
        return payload
