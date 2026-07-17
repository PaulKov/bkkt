"""Backward-compatible facade for drift service.

The implementation lives in :mod:`connectctl.services.drift.service`.
"""

from __future__ import annotations

from .drift.service import DriftService

__all__ = ["DriftService"]
