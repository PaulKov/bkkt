"""Routing (выбор cluster group для deploy/validate/report).

Это публичный фасад (backward-compatible import path). Реальная реализация
разнесена по SRP-модулям:
  - routing_models.py
  - routing_tags.py
  - routing_router.py
  - routing_format.py
"""

from __future__ import annotations

from .routing_format import format_cluster_target  # noqa: F401
from .routing_models import RoutingDecision  # noqa: F401
from .routing_router import ClusterRouter  # noqa: F401
from .routing_tags import norm_tag_list  # noqa: F401

__all__ = [
    "ClusterRouter",
    "RoutingDecision",
    "format_cluster_target",
    "norm_tag_list",
]
