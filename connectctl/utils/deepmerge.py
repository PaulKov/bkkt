from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge override into base (base is not mutated).

    Rules:
    - dict + dict => merge recursively
    - otherwise => override replaces base
    """
    result = deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = deepcopy(val)
    return result
