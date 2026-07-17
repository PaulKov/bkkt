from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


InstallAction = Literal["inserted", "updated", "unchanged"]


@dataclass(frozen=True)
class UpsertBlockResult:
    """Результат upsert операции для marked-block (rc файл)."""

    text: str
    action: InstallAction
    start_marker: str
    end_marker: str
