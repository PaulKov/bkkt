"""Планирование применения коннекторов на основе git diff.

Это модуль-обёртка (facade) для обратной совместимости.
Реальная логика находится в:
- :mod:`connectctl.planning_impl`
- :mod:`connectctl.planning_matchers`
- :mod:`connectctl.planning_scope`
"""

from __future__ import annotations

from .planning_impl import Planner
from .planning_matchers import env_remainder as _env_remainder
from .planning_matchers import match_env_file as _match_env_file

__all__ = ["Planner", "_match_env_file", "_env_remainder"]
