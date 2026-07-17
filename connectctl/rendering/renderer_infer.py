from __future__ import annotations

import re
from typing import Optional


def infer_dataset_from_name(name: str, env: str) -> Optional[str]:
    parts = (name or "").split(".")
    if len(parts) >= 3 and parts[0] == env:
        return parts[2]
    return None


def infer_index_from_name(name: str) -> Optional[str]:
    parts = (name or "").split(".")
    if parts:
        last = parts[-1]
        if last.isdigit():
            return last
    return None


def infer_dataset_from_connector_dir(connector_dir: str) -> Optional[str]:
    d = connector_dir or ""
    d = (
        d.split("connector_", 1)[1]
        if "connector_" in d
        else (d.split("connector-", 1)[1] if "connector-" in d else d)
    )
    if "__" in d:
        cand = d.split("__")[-1]
        return cand or None
    # fallback: first token
    cand = re.split(r"[_-]", d)[0]
    return cand or None
