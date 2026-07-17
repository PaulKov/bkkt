from __future__ import annotations

import re

from .models import UpsertBlockResult


def wrap_rc_block(*, shell: str, prog: str, snippet: str) -> str:
    start = f"# >>> BKKT completion ({shell}) for {prog} >>>"
    end = f"# <<< BKKT completion ({shell}) for {prog} <<<"
    body = snippet.strip("\n")
    return f"{start}\n{body}\n{end}\n"


def upsert_marked_block(existing: str, *, block: str) -> UpsertBlockResult:
    """Idempotent: если блок уже есть — заменяем его целиком.

    Возвращает новый текст + тип действия (inserted/updated/unchanged) и маркеры блока.
    """

    lines = block.splitlines()
    if len(lines) < 2:
        return UpsertBlockResult(
            text=existing, action="unchanged", start_marker="", end_marker=""
        )

    start_marker = lines[0]
    end_marker = lines[-1]
    start = re.escape(start_marker)
    end = re.escape(end_marker)
    pattern = re.compile(start + r"[\s\S]*?" + end + r"\n?", flags=re.MULTILINE)

    m = pattern.search(existing)
    if m:
        current = m.group(0)
        if current == block:
            return UpsertBlockResult(
                text=existing,
                action="unchanged",
                start_marker=start_marker,
                end_marker=end_marker,
            )
        updated = pattern.sub(block, existing)
        return UpsertBlockResult(
            text=updated,
            action="updated",
            start_marker=start_marker,
            end_marker=end_marker,
        )

    # блока нет — добавим в конец
    base = existing
    if base and not base.endswith("\n"):
        base += "\n"
    if base and not base.endswith("\n\n"):
        base += "\n"
    return UpsertBlockResult(
        text=base + block,
        action="inserted",
        start_marker=start_marker,
        end_marker=end_marker,
    )
