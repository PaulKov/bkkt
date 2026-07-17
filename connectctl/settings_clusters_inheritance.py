"""Резолвинг наследования конфигурации cluster groups.

Этот модуль — публичный фасад (backward-compatible import path).
Реальная реализация разнесена по SRP-модулям:
  - settings_clusters_inheritance_parse.py
  - settings_clusters_inheritance_select.py
  - settings_clusters_inheritance_resolver.py
"""

from __future__ import annotations

from .settings_clusters_inheritance_parse import (  # noqa: F401
    FROM_FUNC_NAME,
    FROM_FUNC_RE,
    parse_from_cluster_group_env_call,
)
from .settings_clusters_inheritance_resolver import (  # noqa: F401
    ClusterGroupEnvResolver,
)
from .settings_clusters_inheritance_select import (  # noqa: F401
    select_from_mapping,
)

__all__ = [
    "FROM_FUNC_NAME",
    "FROM_FUNC_RE",
    "parse_from_cluster_group_env_call",
    "select_from_mapping",
    "ClusterGroupEnvResolver",
]
