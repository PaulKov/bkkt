from __future__ import annotations

from typing import Any, List


def norm_tag_list(val: Any) -> List[str]:
    """Нормализация списка тегов.

    Принимает:
      - None → []
      - "tag" → ["tag"]
      - ["a", "b"] → ["a", "b"] (пустые элементы игнорируются)
    """
    if val is None:
        return []
    if isinstance(val, str):
        v = val.strip()
        return [v] if v else []
    if isinstance(val, (list, tuple)):
        out: List[str] = []
        for x in val:
            s = str(x).strip()
            if s:
                out.append(s)
        return out
    s = str(val).strip()
    return [s] if s else []
