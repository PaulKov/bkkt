from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List

from .settings_models import Settings

# Реализация исторически лежала в `cli_helpers.git_changes`.
# Этот модуль даёт публичный API без "_".
from .cli_helpers.git_changes import _expand_renames, _render_for_deleted_path


def expand_renames(changes: Iterable[Any]) -> List[Any]:
    """Раскрыть git rename entries (Rxxx) в пару операций: D + A.

    Это позволяет планировщику/валидатору работать предсказуемо.
    """

    return _expand_renames(changes)


def render_for_deleted_path(
    *, repo_root: Path, base_ref: str, relpath: Path, settings: Settings
) -> str:
    """Best-effort получить имя коннектора для удалённого manifest'а.

    Используется, когда файл удалён, но в отчёте/плане нужно показать `connector.name`.
    """

    return _render_for_deleted_path(
        repo_root=repo_root, base_ref=base_ref, relpath=relpath, settings=settings
    )
