#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List, Tuple


def find_print_calls(code: str) -> List[Tuple[int, int]]:
    """Return list of (lineno, col) where `print(...)` is called."""
    out: List[Tuple[int, int]] = []
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ):
            out.append((getattr(node, "lineno", 0), getattr(node, "col_offset", 0)))
    return out


def main(argv: List[str]) -> int:
    paths = [Path(a) for a in argv[1:]]
    violations: List[str] = []
    for p in paths:
        if p.suffix != ".py":
            continue
        if not p.exists():
            continue
        try:
            code = p.read_text(encoding="utf-8")
        except Exception as e:
            violations.append(f"{p}: не удалось прочитать файл: {e}")
            continue
        try:
            calls = find_print_calls(code)
        except SyntaxError as e:
            violations.append(f"{p}:{e.lineno}:{e.offset}: syntax error: {e.msg}")
            continue
        for lineno, col in calls:
            violations.append(
                f"{p}:{lineno}:{col}: найден print() (используйте logging через BKKT LOG)"
            )
    if violations:
        sys.stderr.write("BKKT pre-commit: print() запрещён\n")
        for v in violations:
            sys.stderr.write(f"  - {v}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
