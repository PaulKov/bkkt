from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class NoPrintIssue:
    path: Path
    lineno: int
    col: int
    preview: str


def find_print_calls(paths: Iterable[Path]) -> List[NoPrintIssue]:
    """Найти вызовы `print(...)` в Python файлах.

    Используем AST, чтобы не ловить ложные срабатывания (например, строки "print(").
    """

    issues: List[NoPrintIssue] = []

    for p in paths:
        try:
            src = p.read_text(encoding="utf-8")
        except Exception:
            continue

        try:
            tree = ast.parse(src, filename=str(p))
        except SyntaxError:
            # Не ломаем lint из-за чужих/вспомогательных файлов.
            continue

        lines = src.splitlines()

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            func = node.func
            if isinstance(func, ast.Name) and func.id == "print":
                lineno = int(getattr(node, "lineno", 1) or 1)
                col = int(getattr(node, "col_offset", 0) or 0)
                preview = ""
                try:
                    preview = lines[lineno - 1].rstrip()
                except Exception:
                    preview = "print(...)"
                issues.append(
                    NoPrintIssue(path=p, lineno=lineno, col=col, preview=preview)
                )

    return issues


def iter_python_files(*, repo_root: Path, scope: str) -> Sequence[Path]:
    """Собрать список Python файлов по scope."""

    if scope == "all":
        bases = [repo_root]
    else:
        bases = [repo_root / "connectctl"]

    out: List[Path] = []
    for base in bases:
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            # игнорируем virtualenv/cache
            if any(
                part in {".venv", "venv", "__pycache__", ".pytest_cache"}
                for part in p.parts
            ):
                continue
            out.append(p)
    return out


def build_no_print_markdown(
    issues: Sequence[NoPrintIssue], *, max_items: int = 20
) -> str:
    if not issues:
        return "### ✅ Запрещённых вызовов print() не найдено\n"

    lines: List[str] = []
    lines.append("### ❌ Найдены запрещённые вызовы print()")
    lines.append("")

    show = list(issues)[: max_items if max_items > 0 else len(issues)]
    for it in show:
        rel = it.path.as_posix()
        lines.append(f"- `{rel}:{it.lineno}:{it.col}` — `{it.preview.strip()}`")

    if max_items > 0 and len(issues) > max_items:
        lines.append(f"- … и ещё **{len(issues) - max_items}**")

    lines.append("")
    lines.append(
        "Это **hard-error**: print() запрещён. Используйте BKKT LOG (logging + DI)."
    )

    return "\n".join(lines) + "\n"
