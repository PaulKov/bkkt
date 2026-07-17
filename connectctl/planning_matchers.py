from __future__ import annotations

import re

from .models import Environment


_ENV_FILE_UNDERSCORE_RE = re.compile(
    r"^(dev|stage|prod)_(source|sink)_.+\.json$", re.IGNORECASE
)
_ENV_FILE_DOT_RE = re.compile(
    r"^(dev|stage|prod)\..*(?:\.source\.|\.sink\.).+\.json$", re.IGNORECASE
)
_BASE_FILE_RE = re.compile(r"^base\.(.+)\.json$", re.IGNORECASE)


def match_env_file(name: str):
    """Вернуть `(env, style)` если это deployable env manifest, иначе `None`."""
    m = _ENV_FILE_UNDERSCORE_RE.match(name)
    if m:
        return Environment.from_str(m.group(1).lower()), "underscore"
    m = _ENV_FILE_DOT_RE.match(name)
    if m:
        return Environment.from_str(m.group(1).lower()), "dot"
    return None


def env_remainder(name: str) -> str | None:
    """Вернуть всё после '<env>_' или '<env>.' включая .json."""
    m = _ENV_FILE_UNDERSCORE_RE.match(name)
    if m:
        return name.split("_", 1)[1]
    m = _ENV_FILE_DOT_RE.match(name)
    if m:
        return name.split(".", 1)[1]
    return None


def match_base_file(name: str):
    """Вернуть match для base-файла `base.<...>.json` или None."""
    return _BASE_FILE_RE.match(name)
