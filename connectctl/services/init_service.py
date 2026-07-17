"""Backwards-compatible facade for :class:`InitService`.

Refactor stage 18:
- The original `connectctl.services.init_service` was a single large module.
- The implementation was split into small SRP modules under `connectctl.services.init`.

This file keeps the import path stable:

    from connectctl.services.init_service import InitService

"""

from __future__ import annotations

from .init.service import InitService

__all__ = ["InitService"]
