from __future__ import annotations

from dataclasses import dataclass
import textwrap
from typing import Iterable, Literal, Mapping, Sequence


Alignment = Literal["left", "right"]


@dataclass(frozen=True)
class TableColumn:
    """Column metadata for deterministic terminal table rendering."""

    key: str
    title: str
    max_width: int = 32
    align: Alignment = "left"


TableRow = Mapping[str, object]


def render_terminal_table(
    columns: Sequence[TableColumn], rows: Sequence[TableRow]
) -> str:
    """Render a terminal-friendly table with multiline cells.

    This helper is intentionally dependency-free and deterministic: BKKT text
    output is used in runbooks, CI logs and Slack copy-paste, where markdown
    tables with HTML ``<br>`` are hard to read. Machine outputs must keep using
    JSON/YAML instead.
    """

    widths = _column_widths(columns, rows)
    parts = [_border("top", widths)]
    parts.extend(_render_line([col.title for col in columns], columns, widths))
    parts.append(_border("header", widths))
    for row in rows:
        cells = [_cell_lines(row.get(col.key, ""), col.max_width) for col in columns]
        height = max((len(cell) for cell in cells), default=1)
        for index in range(height):
            parts.extend(
                _render_line(
                    [cell[index] if index < len(cell) else "" for cell in cells],
                    columns,
                    widths,
                )
            )
    parts.append(_border("bottom", widths))
    return "\n".join(parts)


def format_lines(values: Iterable[object]) -> str:
    """Format a sequence as real multiline terminal text."""

    materialized = [str(value) for value in values if str(value)]
    return "\n".join(materialized) if materialized else "-"


def _column_widths(
    columns: Sequence[TableColumn], rows: Sequence[TableRow]
) -> list[int]:
    widths: list[int] = []
    for col in columns:
        candidates = [col.title]
        for row in rows:
            candidates.extend(_cell_lines(row.get(col.key, ""), col.max_width))
        natural = max((len(item) for item in candidates), default=len(col.title))
        widths.append(min(max(natural, len(col.title)), col.max_width))
    return widths


def _cell_lines(value: object, max_width: int) -> list[str]:
    text = "" if value is None else str(value)
    if not text:
        return [""]

    lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        if not raw_line:
            lines.append("")
            continue
        wrapped = textwrap.wrap(
            raw_line,
            width=max_width,
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=False,
            drop_whitespace=False,
        )
        lines.extend(wrapped or [""])
    return lines


def _render_line(
    values: Sequence[str], columns: Sequence[TableColumn], widths: Sequence[int]
) -> list[str]:
    rendered = []
    for value, col, width in zip(values, columns, widths):
        rendered.append(_align(value, width, col.align))
    return ["│ " + " │ ".join(rendered) + " │"]


def _align(value: str, width: int, align: Alignment) -> str:
    return value.rjust(width) if align == "right" else value.ljust(width)


def _border(kind: Literal["top", "header", "bottom"], widths: Sequence[int]) -> str:
    chars = {
        "top": ("┌", "┬", "┐"),
        "header": ("├", "┼", "┤"),
        "bottom": ("└", "┴", "┘"),
    }[kind]
    return chars[0] + chars[1].join("─" * (width + 2) for width in widths) + chars[2]


__all__ = ["TableColumn", "format_lines", "render_terminal_table"]
