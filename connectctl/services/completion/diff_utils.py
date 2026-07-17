from __future__ import annotations

import difflib


def format_unified_diff(
    old_text: str,
    new_text: str,
    *,
    fromfile: str,
    tofile: str,
    max_lines: int = 200,
) -> str:
    """Сформировать unified diff.

    - Возвращает пустую строку, если изменений нет.
    - `max_lines` ограничивает длину диффа (по умолчанию 200 строк).
    """

    diff_lines = list(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
    )
    if not diff_lines:
        return ""
    if max_lines > 0 and len(diff_lines) > max_lines:
        hidden = len(diff_lines) - max_lines
        diff_lines = diff_lines[:max_lines] + [f"... (ещё {hidden} строк скрыто)"]
    return "\n".join(diff_lines).rstrip() + "\n"
