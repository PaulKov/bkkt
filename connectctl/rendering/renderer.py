"""Facade for connector rendering.

Refactor stage 21:
  - split the old monolithic renderer implementation into small SRP modules
  - keep backwards-compatible imports: `from connectctl.rendering.renderer import ConnectorRenderer`.
"""

from __future__ import annotations

from .renderer_impl import ConnectorRenderer
from .renderer_models import RenderResult, VarUsage

__all__ = ["ConnectorRenderer", "RenderResult", "VarUsage"]
