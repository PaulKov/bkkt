"""Планировщик экспорта (фасад).

Исторически модуль :mod:`connectctl.export.planner` содержал всю логику экспорта
в одном файле. На этапе рефакторинга код разнесён по небольшим SRP-модулям:

- :mod:`connectctl.export.planner_generic` — построение базовых planned-файлов
- :mod:`connectctl.export.planner_delta` — вычисление delta между rendered и remote
- :mod:`connectctl.export.planner_io` — материализация planned-файлов в репозиторий
- :mod:`connectctl.export.planner_export` — “умный” экспорт с reuse-overrides

Этот модуль оставлен как **стабильный фасад**:
команды/сервисы продолжают импортировать публичные функции отсюда.
"""

from __future__ import annotations

from .planner_delta import compute_delta_for_remote_keys
from .planner_export import export_connector_to_repo
from .planner_generic import build_generic_planned_files
from .planner_io import apply_plan_to_repo

__all__ = [
    "apply_plan_to_repo",
    "build_generic_planned_files",
    "compute_delta_for_remote_keys",
    "export_connector_to_repo",
]
