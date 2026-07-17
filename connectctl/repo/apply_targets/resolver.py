"""Apply targets resolver (facade).

`resolve_apply_targets()` используется в apply pipeline и импортируется как:

- `from connectctl.repo.apply_targets import resolve_apply_targets`

Реализация разнесена по SRP-модулям:
- resolver_impl.py
- resolve_existing.py
- resolve_missing.py
- resolve_items.py
"""

from __future__ import annotations

from .resolver_impl import resolve_apply_targets

__all__ = ["resolve_apply_targets"]
