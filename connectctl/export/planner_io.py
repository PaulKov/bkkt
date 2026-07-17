from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Mapping, Optional

from ..adapters.filesystem import LocalFileSystem
from ..ports import FileSystem


def _write_json(path: Path, obj: Mapping[str, Any], *, fs: FileSystem) -> None:
    raw = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fs.write_text(path, raw, encoding="utf-8")


def apply_plan_to_repo(
    planned_files: Mapping[Path, Any],
    *,
    dry_run: bool,
    force: bool,
    fs: Optional[FileSystem] = None,
) -> List[Path]:
    """Записать planned-файлы в репозиторий.

    Используется командой/сервисом `export` для материализации плана.

    Правила:
    - порядок детерминированный (sort по пути)
    - если файл существует и `force=False` — пропускаем
    - при `dry_run=True` — ничего не пишем

    DI:
    - запись/проверка файлов делается через FileSystem порт.
      Это позволяет тестировать генерацию без реального диска.
    """

    fs = fs or LocalFileSystem()

    written: List[Path] = []

    for path in sorted(planned_files.keys()):
        obj = planned_files[path]
        path = Path(path)

        if fs.exists(path) and not force:
            continue

        if dry_run:
            continue

        _write_json(path, obj, fs=fs)
        written.append(path)

    return written
