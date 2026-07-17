from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Sequence, Tuple

from .patch_io_kv import _PATCH_DELETE_TOKENS


def _split_patch_set_and_delete(
    patch_raw: Mapping[str, Any]
) -> Tuple[Dict[str, str], Sequence[str]]:
    """Split a patch payload into (set_values, delete_keys).

    Kafka Connect configs are effectively a string map.

    Patch sources may include special *deletion* intent:
      - JSON: {"some.key": null}  -> delete key from config
      - key=value: some.key=__DELETE__ (or __REMOVE__/__UNSET__) -> delete

    Everything else is coerced to strings:
      - dict/list are JSON-encoded
      - numbers/bools become strings
      - empty string remains empty string (this is NOT deletion)
    """

    to_set: Dict[str, str] = {}
    to_delete: list[str] = []

    for k, v in (patch_raw or {}).items():
        key = str(k)

        if v is None:
            to_delete.append(key)
            continue

        if isinstance(v, str) and v.strip().upper() in _PATCH_DELETE_TOKENS:
            to_delete.append(key)
            continue

        if isinstance(v, (dict, list)):
            to_set[key] = json.dumps(v, ensure_ascii=False)
        else:
            to_set[key] = str(v)

    return to_set, to_delete


__all__ = ["_split_patch_set_and_delete"]
