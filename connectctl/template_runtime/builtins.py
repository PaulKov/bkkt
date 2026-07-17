from __future__ import annotations

import hashlib
from typing import Any


def hash_int(value: Any, *, mod: int = 2147483647, salt: str = "") -> str:
    """Deterministic integer hash for stable connector IDs."""

    if mod is None:
        mod = 2147483647
    try:
        mod_i = int(mod)
    except Exception as e:
        raise ValueError(f"mod must be int, got {mod!r}") from e

    s = f"{salt}\x1f{value}" if salt else str(value)
    digest = hashlib.sha256(s.encode("utf-8")).digest()
    n = int.from_bytes(digest[:8], "big", signed=False)
    if mod_i <= 1:
        return "0"
    return str(1 + (n % (mod_i - 1)))


BUILTIN_FUNCTIONS = {
    "hash_int": (
        hash_int,
        "Deterministic integer hash for stable IDs such as database.server.id.",
    ),
}
