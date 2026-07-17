from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Set

from ..exceptions import ValidationError


_ALLOWED_SEVERITIES: Set[str] = {"error", "warning"}


@dataclass(frozen=True)
class ConfigTestIssue:
    severity: str  # 'error' | 'warning'
    rule_id: str
    message: str
    key: Optional[str] = None


def _as_list(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, (list, tuple)):
        return list(x)
    return [x]


def _ensure_str(x: Any, *, key: str) -> str:
    if isinstance(x, str):
        return x
    raise ValidationError(
        f"config_tests: value for {key!r} must be a string (got {type(x).__name__})"
    )
