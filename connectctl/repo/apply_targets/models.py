from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class ApplyItem:
    """Одна цель деплоя (один файл/виртуальный файл для apply).

    Поля:
      - actual_path: путь к файлу на диске, который будет прочитан/использован как слой.
      - requested_path: "виртуальный" путь (используется для инференса имени и vars).
        Для обычных файлов requested_path == actual_path.
      - runtime_vars: переменные уровня item (например, index из instances.json).
      - runtime_var_sources: map dot-key -> строка-источник.
      - is_virtual: True, если requested_path не существует и получается из template.
    """

    actual_path: Path
    requested_path: Path
    runtime_vars: Dict[str, Any]
    runtime_var_sources: Dict[str, str]
    is_virtual: bool = False


@dataclass(frozen=True)
class TemplateExpansionEvent:
    template_path: Path
    source: str
    generated: Tuple[Path, ...]
    skipped_existing: Tuple[Path, ...]


@dataclass(frozen=True)
class ApplyTargets:
    items: List[ApplyItem]
    template_mappings: List[Tuple[Path, Path]]
    expansions: List[TemplateExpansionEvent]
