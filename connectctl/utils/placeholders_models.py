from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlaceholderUse:
    key: str
    source: str  # context|os_env|default|fn_arg|unresolved
    value: Optional[str] = None


@dataclass
class PlaceholderTrace:
    """Трассировка: какие плейсхолдеры реально использовались при рендеринге."""

    uses: list[PlaceholderUse] = field(default_factory=list)

    def add(self, key: str, source: str, value: Optional[str] = None) -> None:
        self.uses.append(PlaceholderUse(key=key, source=source, value=value))
