from __future__ import annotations

from typing import List, Sequence


def dedup_tags(tags: Sequence[str]) -> List[str]:
    """De-duplicate tags while preserving order."""

    seen = set()
    out: List[str] = []
    for t in tags:
        s = str(t).strip()
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out
