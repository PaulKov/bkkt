from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping


def merge_config_with_deletes(
    base: Mapping[str, Any], override: Mapping[str, Any]
) -> Dict[str, Any]:
    """Merge config fragments with explicit delete semantics.

    Rules:
    - dict + dict => merge recursively
    - any non-dict override replaces the previous value
    - ``null`` (Python ``None``) in the override removes the key from the result

    This helper is intentionally used only for connector ``config`` fragments.
    We do not apply delete semantics to ``vars`` or ``connectctl`` metadata.
    """

    result: Dict[str, Any] = deepcopy(dict(base))
    for key, value in override.items():
        key_s = str(key)

        if value is None:
            result.pop(key_s, None)
            continue

        current = result.get(key_s)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged = merge_config_with_deletes(current, value)
            if merged:
                result[key_s] = merged
            else:
                result.pop(key_s, None)
        else:
            result[key_s] = deepcopy(value)

    return result
