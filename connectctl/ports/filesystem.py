"""Порт (интерфейс) файловой системы.

Цель:
- сервисы BKKT (init/export/apply/put-config и др.) активно читают/пишут файлы;
- при DI через FileSystem можно тестировать сервисы без реального диска,
  используя in-memory реализацию.

Важно:
- Это *опциональный* порт: по умолчанию используется LocalFileSystem.
- Мы не пытаемся завернуть ВСЕ операции Path/OS — только те, которые нужны
  для сервисного слоя и юнит-тестов.
"""

from __future__ import annotations
from pathlib import Path
from typing import Iterable, Protocol


class FileSystem(Protocol):
    """Минимальный набор операций, который используют сервисы."""

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str: ...

    def write_text(self, path: Path, data: str, *, encoding: str = "utf-8") -> None: ...

    def exists(self, path: Path) -> bool: ...

    def is_file(self, path: Path) -> bool: ...

    def is_dir(self, path: Path) -> bool: ...

    def mkdirs(self, path: Path, *, exist_ok: bool = True) -> None: ...

    def iterdir(self, path: Path) -> Iterable[Path]: ...

    def glob(self, root: Path, pattern: str) -> Iterable[Path]: ...

    def remove(self, path: Path) -> None: ...

    def rename(self, src: Path, dst: Path) -> None: ...
