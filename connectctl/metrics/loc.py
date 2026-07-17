from __future__ import annotations

import io
import statistics
import token
import tokenize
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from .models import LocStats


def iter_py_files(root: Path) -> Iterable[Path]:
    """Итерировать Python файлы, игнорируя типичные служебные каталоги."""

    ignore_dirs = {
        ".git",
        ".venv",
        ".cache",
        "__pycache__",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".eggs",
        "rendered",
    }

    for p in root.rglob("*.py"):
        if set(p.parts) & ignore_dirs:
            continue
        if any(part.startswith(".test_venv") for part in p.parts):
            continue
        yield p


def count_lines(text: str) -> int:
    """Количество строк (приближение к `wc -l`)."""

    return len(text.splitlines())


def count_sloc(text: str) -> int:
    """Count source lines of code.

    SLOC excludes:
    - blank lines
    - comment-only lines

    It keeps lines with actual Python tokens, including docstrings and lines
    that contain code with inline comments.
    """

    significant_lines: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type in {
                token.ENDMARKER,
                token.NEWLINE,
                tokenize.NL,
                token.INDENT,
                token.DEDENT,
                tokenize.COMMENT,
                getattr(tokenize, "ENCODING", -1),
            }:
                continue
            significant_lines.add(tok.start[0])
    except (tokenize.TokenError, IndentationError):
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                significant_lines.add(line_no)
    return len(significant_lines)


def is_test_python_file(path: Path) -> bool:
    name = path.name
    if name == "conftest.py":
        return True
    if name.startswith("test_") and name.endswith(".py"):
        return True
    return "tests" in path.parts


def calc_loc_stats(files: Sequence[Path], *, root: Path, top_n: int) -> LocStats:
    items: List[Tuple[str, int, int]] = []
    total = 0
    total_sloc = 0
    min_lines = 10**9
    min_path = ""
    max_lines = -1
    max_path = ""

    for f in files:
        text = f.read_text(encoding="utf-8")
        n = count_lines(text)
        sloc = count_sloc(text)
        rel = str(f.relative_to(root)).replace("\\", "/")
        items.append((rel, n, sloc))
        total += n
        total_sloc += sloc
        if n < min_lines or (n == min_lines and (not min_path or rel < min_path)):
            min_lines = n
            min_path = rel
        if n > max_lines or (n == max_lines and (not max_path or rel < max_path)):
            max_lines = n
            max_path = rel

    counts = sorted((n for _, n, _ in items))
    sloc_counts = sorted((n for _, _, n in items))
    avg = (total / len(items)) if items else 0.0
    avg_sloc = (total_sloc / len(items)) if items else 0.0
    med = float(statistics.median(counts)) if counts else 0.0
    med_sloc = float(statistics.median(sloc_counts)) if sloc_counts else 0.0
    top = sorted(items, key=lambda x: (-x[1], x[0]))[: max(0, top_n)]

    if not items:
        min_lines = 0
        max_lines = 0

    return LocStats(
        files=len(items),
        total_lines=total,
        total_sloc=total_sloc,
        min_lines=min_lines,
        min_path=min_path,
        max_lines=max_lines,
        max_path=max_path,
        avg_lines=float(avg),
        median_lines=float(med),
        avg_sloc=float(avg_sloc),
        median_sloc=float(med_sloc),
        top=top,
    )
