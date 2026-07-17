from __future__ import annotations

import copy
from typing import Any, Dict, Mapping

from .exceptions import ConfigError

from .settings_clusters_inheritance_parse import FROM_FUNC_NAME


def _get_by_path(obj: Mapping[str, Any], path: str) -> Any:
    cur: Any = obj
    parts = [p for p in path.split(".") if p]
    for p in parts:
        if not isinstance(cur, Mapping) or p not in cur:
            raise ConfigError(
                f"{FROM_FUNC_NAME}(): path '{path}' not found in referenced cluster group config"
            )
        cur = cur[p]
    return cur


def select_from_mapping(base: Mapping[str, Any], selector: str) -> Any:
    """Выбрать значение(я) из base mapping.

    selector:
      - "all" → deep copy всего mapping
      - "kafka" или "connect.port" → значение по dot-path
      - "connect.hosts,connect.port" → mapping с только выбранными параметрами
    """
    sel = (selector or "").strip()
    if not sel or sel.lower() == "all":
        return copy.deepcopy(dict(base))

    paths = [p.strip() for p in sel.split(",") if p.strip()]
    if not paths:
        return copy.deepcopy(dict(base))

    if len(paths) == 1:
        return copy.deepcopy(_get_by_path(base, paths[0]))

    out: Dict[str, Any] = {}
    for path in paths:
        val = _get_by_path(base, path)
        parts = [p for p in path.split(".") if p]
        cur = out
        for p in parts[:-1]:
            if p not in cur or not isinstance(cur.get(p), dict):
                cur[p] = {}
            cur = cur[p]
        cur[parts[-1]] = copy.deepcopy(val)
    return out
