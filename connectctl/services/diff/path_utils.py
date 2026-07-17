from __future__ import annotations

from pathlib import Path


def relpath_safe(p: Path, *, base: Path) -> str:
    """Best-effort относительный путь (для репортов).

    Нельзя падать на странных путях/resolve/не-существующих файлах.
    """

    try:
        if p.is_absolute() and base in p.parents:
            return str(p.relative_to(base))
    except Exception:
        pass
    return str(p)
