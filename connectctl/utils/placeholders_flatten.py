from __future__ import annotations

from typing import Any, Dict, Mapping


def flatten_dict(d: Mapping[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Сделать плоский словарь из вложенной структуры, используя dot-ключи.

    Пример:
      {"a": {"b": 1}} -> {"a.b": 1}
    """
    out: Dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, Mapping):
            out.update(flatten_dict(v, key))
        else:
            out[key] = v
    return out
