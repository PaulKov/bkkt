"""Backward-compatible facade for diff service.

Реализация находится в :mod:`connectctl.services.diff.service`.
"""

from __future__ import annotations

from .diff.service import DiffService

__all__ = ["DiffService"]
