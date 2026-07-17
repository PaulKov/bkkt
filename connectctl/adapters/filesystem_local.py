from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from ..ports.filesystem import FileSystem


class LocalFileSystem(FileSystem):
    """Реальная файловая система (default)."""

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        return Path(path).read_text(encoding=encoding)

    def write_text(self, path: Path, data: str, *, encoding: str = "utf-8") -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data, encoding=encoding)

    def exists(self, path: Path) -> bool:
        return Path(path).exists()

    def is_file(self, path: Path) -> bool:
        return Path(path).is_file()

    def is_dir(self, path: Path) -> bool:
        return Path(path).is_dir()

    def mkdirs(self, path: Path, *, exist_ok: bool = True) -> None:
        Path(path).mkdir(parents=True, exist_ok=exist_ok)

    def iterdir(self, path: Path) -> Iterable[Path]:
        return list(Path(path).iterdir())

    def glob(self, root: Path, pattern: str) -> Iterable[Path]:
        return list(Path(root).glob(pattern))

    def remove(self, path: Path) -> None:
        p = Path(path)
        if p.is_dir():
            # best-effort recursive remove for small test artifacts
            for child in p.glob("**/*"):
                if child.is_file():
                    child.unlink(missing_ok=True)
            for child in sorted(p.glob("**/*"), reverse=True):
                if child.is_dir():
                    try:
                        child.rmdir()
                    except Exception:
                        pass
            try:
                p.rmdir()
            except Exception:
                pass
            return
        p.unlink(missing_ok=True)

    def rename(self, src: Path, dst: Path) -> None:
        s = Path(src)
        d = Path(dst)
        d.parent.mkdir(parents=True, exist_ok=True)
        os.replace(s, d)
