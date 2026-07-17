from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Set

from ..ports.filesystem import FileSystem


@dataclass
class InMemoryFileSystem(FileSystem):
    """Простейшая in-memory FS для юнит-тестов сервисов.

    Ограничения:
    - хранит только текстовые файлы
    - поддерживает базовые операции (read/write/exists/mkdirs/glob/iterdir)

    Для тестов BKKT этого обычно достаточно.
    """

    files: Dict[str, str] = field(default_factory=dict)
    dirs: Set[str] = field(default_factory=lambda: {"."})

    def _norm(self, path: Path) -> str:
        s = str(path)
        s = s.replace("\\", "/")
        # strip trailing slash
        if s.endswith("/") and s != "/":
            s = s.rstrip("/")
        return s

    def _parent(self, p: str) -> str:
        if "/" not in p:
            return "."
        parent = p.rsplit("/", 1)[0]
        return parent or "/"

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        p = self._norm(path)
        if p not in self.files:
            raise FileNotFoundError(p)
        return self.files[p]

    def write_text(self, path: Path, data: str, *, encoding: str = "utf-8") -> None:
        p = self._norm(path)
        parent = self._parent(p)
        self.mkdirs(Path(parent), exist_ok=True)
        self.files[p] = data

    def exists(self, path: Path) -> bool:
        p = self._norm(path)
        return p in self.files or p in self.dirs

    def is_file(self, path: Path) -> bool:
        return self._norm(path) in self.files

    def is_dir(self, path: Path) -> bool:
        return self._norm(path) in self.dirs

    def mkdirs(self, path: Path, *, exist_ok: bool = True) -> None:
        p = self._norm(path)
        # create parent chain
        parts = [x for x in p.split("/") if x and x != "."]
        cur = "." if not p.startswith("/") else "/"
        if cur == "/":
            self.dirs.add("/")
        for part in parts:
            if cur in {".", "/"}:
                cur = f"{cur}{part}" if cur == "/" else part
            else:
                cur = f"{cur}/{part}"
            self.dirs.add(cur)

    def iterdir(self, path: Path) -> Iterable[Path]:
        p = self._norm(path)
        if p not in self.dirs:
            return []
        prefix = "" if p in {".", "/"} else p + "/"
        seen: Set[str] = set()
        out: list[Path] = []

        # dirs
        for d in self.dirs:
            if not d.startswith(prefix) or d == p:
                continue
            rest = d[len(prefix) :]
            if "/" in rest:
                rest = rest.split("/", 1)[0]
            if rest and rest not in seen:
                seen.add(rest)
                out.append(Path(prefix + rest) if prefix else Path(rest))

        # files
        for f in self.files.keys():
            if not f.startswith(prefix):
                continue
            rest = f[len(prefix) :]
            if "/" in rest:
                rest = rest.split("/", 1)[0]
            if rest and rest not in seen:
                seen.add(rest)
                out.append(Path(prefix + rest) if prefix else Path(rest))

        return out

    def glob(self, root: Path, pattern: str) -> Iterable[Path]:
        """Минимальная, но достаточно близкая к `Path.glob()` реализация glob.

        Поддержка:
        - сегмент `**` означает "0 или более" сегментов пути
        - `*`, `?`, `[]` матчятся внутри одного сегмента
        - сопоставление анкерено относительно `root`

        Это делает in-memory FS полезной для тестов `apply/export/render/...` без диска.
        """

        r = self._norm(root)

        # Префикс для отбора кандидатов.
        # Для root="/" префикс — "/", а относительная часть (rel) без ведущего "/".
        if r == "/":
            prefix = "/"
        elif r in {".", ""}:
            prefix = ""
        else:
            prefix = r + "/"

        pat_parts = tuple([p for p in pattern.split("/") if p and p != "."])

        @lru_cache(maxsize=None)
        def _match(path_parts: tuple[str, ...], i: int, j: int) -> bool:
            if j == len(pat_parts):
                return i == len(path_parts)
            pat = pat_parts[j]
            if pat == "**":
                # '**' может матчить 0 сегментов
                if _match(path_parts, i, j + 1):
                    return True
                # или 1+ сегментов
                if i < len(path_parts) and _match(path_parts, i + 1, j):
                    return True
                return False
            if i >= len(path_parts):
                return False
            if fnmatch.fnmatchcase(path_parts[i], pat):
                return _match(path_parts, i + 1, j + 1)
            return False

        out: list[Path] = []
        for full in self.files.keys():
            if prefix:
                if not full.startswith(prefix):
                    continue
                rel = full[len(prefix) :]
            else:
                rel = full[1:] if (r == "/" and full.startswith("/")) else full

            path_parts = tuple([p for p in rel.split("/") if p and p != "."])
            if _match(path_parts, 0, 0):
                out.append(Path(full))

        return out

    def remove(self, path: Path) -> None:
        p = self._norm(path)
        self.files.pop(p, None)
        # do not auto-prune dirs

    def rename(self, src: Path, dst: Path) -> None:
        s = self._norm(src)
        d = self._norm(dst)
        if s in self.files:
            self.files[d] = self.files.pop(s)
            self.mkdirs(Path(self._parent(d)), exist_ok=True)
