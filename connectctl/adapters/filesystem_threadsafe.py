from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..ports import FileSystem


@dataclass
class ThreadSafeFileSystem(FileSystem):
    """Тонкий wrapper над FileSystem, добавляющий thread-safety.

    Зачем:
    - некоторые команды (apply/export/connect bulk) могут работать в ThreadPool
    - in-memory FS в тестах и даже local FS операции записи могут выполняться конкурентно
    - нам нужна простая гарантия "не сломаемся" при параллельных write/remove/rename

    Реализация максимально простая (KISS): один глобальный Lock.
    Это достаточно для корректности и тестируемости.
    """

    base: FileSystem

    def __post_init__(self) -> None:
        self._lock = threading.RLock()

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        with self._lock:
            return self.base.read_text(path, encoding=encoding)

    def write_text(self, path: Path, data: str, *, encoding: str = "utf-8") -> None:
        with self._lock:
            self.base.write_text(path, data, encoding=encoding)

    def exists(self, path: Path) -> bool:
        with self._lock:
            return self.base.exists(path)

    def is_file(self, path: Path) -> bool:
        with self._lock:
            return self.base.is_file(path)

    def is_dir(self, path: Path) -> bool:
        with self._lock:
            return self.base.is_dir(path)

    def mkdirs(self, path: Path, *, exist_ok: bool = True) -> None:
        with self._lock:
            self.base.mkdirs(path, exist_ok=exist_ok)

    def iterdir(self, path: Path) -> Iterable[Path]:
        with self._lock:
            return list(self.base.iterdir(path))

    def glob(self, root: Path, pattern: str) -> Iterable[Path]:
        with self._lock:
            return list(self.base.glob(root, pattern))

    def remove(self, path: Path) -> None:
        with self._lock:
            self.base.remove(path)

    def rename(self, src: Path, dst: Path) -> None:
        with self._lock:
            self.base.rename(src, dst)


__all__ = ["ThreadSafeFileSystem"]
