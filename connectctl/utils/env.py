from __future__ import annotations

import os
import re
from typing import Any


_ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)(:-([^}]*))?\}")


def expand_env_vars(value: str) -> str:
    """Expand ${VAR} or ${VAR:-default} in a string."""

    def repl(match: re.Match[str]) -> str:
        var = match.group(1)
        default = match.group(3)  # may be None
        return os.environ.get(var, default if default is not None else "")

    return _ENV_RE.sub(repl, value)


def expand_env_in_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return expand_env_vars(obj)
    if isinstance(obj, list):
        return [expand_env_in_obj(v) for v in obj]
    if isinstance(obj, dict):
        return {k: expand_env_in_obj(v) for k, v in obj.items()}
    return obj
