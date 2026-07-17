from __future__ import annotations

from pathlib import Path
from typing import List

from ...ports import FileSystem

_GLOB_CHARS = set("*?[")


def has_glob(s: str) -> bool:
    return any(ch in s for ch in _GLOB_CHARS)


def expand_globs(
    raw: str, repo_root: Path, *, fs: FileSystem | None = None
) -> List[Path]:
    """Развернуть glob-выражение относительно repo_root.

    Поддерживает и абсолютные пути.
    """

    p = Path(raw)
    if p.is_absolute():
        base = Path("/")
        pattern = str(p)[1:]
    else:
        base = repo_root
        pattern = raw

    if not has_glob(pattern):
        return [p if p.is_absolute() else (repo_root / p)]

    it = fs.glob(base, pattern) if fs else base.glob(pattern)
    out: List[Path] = []
    for x in it:
        if fs:
            if not fs.exists(x):
                continue
        else:
            if not x.exists():
                continue
        out.append(x)
    return out
