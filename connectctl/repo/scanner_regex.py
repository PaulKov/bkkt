from __future__ import annotations

import re
from typing import Optional, Tuple


# Исторически репозиторий поддерживал underscore-style манифесты.
# Сейчас стандарт — dot-style, но underscore оставлен ради обратной совместимости.

DEPLOYABLE_UNDERSCORE_RE = re.compile(
    r"^(dev|stage|prod)_(source|sink)_.+\.json$", re.IGNORECASE
)
DEPLOYABLE_DOT_RE = re.compile(
    r"^(dev|stage|prod)\..*(?:\.source\.|\.sink\.).+\.json$", re.IGNORECASE
)
BASE_FILE_RE = re.compile(r"^base\.(.+)\.json$", re.IGNORECASE)


def is_deployable_connector_filename(name: str) -> bool:
    return bool(DEPLOYABLE_UNDERSCORE_RE.match(name) or DEPLOYABLE_DOT_RE.match(name))


def match_deployable(
    name: str,
) -> Tuple[Optional[re.Match[str]], Optional[re.Match[str]]]:
    return DEPLOYABLE_UNDERSCORE_RE.match(name), DEPLOYABLE_DOT_RE.match(name)


def is_base_filename(name: str) -> bool:
    return bool(BASE_FILE_RE.match(name))
