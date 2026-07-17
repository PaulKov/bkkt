from __future__ import annotations

from pathlib import Path
from typing import List

from .models import ApplyItem


def make_nonvirtual_item(path: Path) -> ApplyItem:
    p = path.resolve()
    return ApplyItem(
        actual_path=p,
        requested_path=p,
        runtime_vars={},
        runtime_var_sources={},
        is_virtual=False,
    )


def make_virtual_item(
    *,
    template_path: Path,
    requested_path: Path,
    runtime_vars: dict,
    runtime_var_sources: dict,
) -> ApplyItem:
    return ApplyItem(
        actual_path=template_path.resolve(),
        requested_path=requested_path.resolve(),
        runtime_vars=runtime_vars,
        runtime_var_sources=runtime_var_sources,
        is_virtual=True,
    )


def add_unique_item(items: List[ApplyItem], it: ApplyItem) -> bool:
    """Add item if requested_path is not yet present. Returns True if added."""

    for ex in items:
        if ex.requested_path == it.requested_path:
            return False
    items.append(it)
    return True
