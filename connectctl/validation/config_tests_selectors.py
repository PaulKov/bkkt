from __future__ import annotations

import fnmatch
import re
from typing import Any, Dict, Optional, Sequence

from ..models import ConnectorManifest, ConnectorType

from .config_tests_common import _as_list


def _match_one(value: str, pattern: str) -> bool:
    """Match a single selector pattern.

    Supported forms:
      - exact match: "prod"
      - glob: "prod*" / "connector_*"
      - regex: "re:^prod\\..*" (fullmatch)
    """

    if pattern.startswith("re:"):
        rx = pattern[3:]
        return re.fullmatch(rx, value) is not None
    if any(ch in pattern for ch in "*?"):
        return fnmatch.fnmatch(value, pattern)
    return value == pattern


def _match_any(value: str, patterns: Sequence[str]) -> bool:
    return any(_match_one(value, str(p)) for p in patterns)


def _selector_value(
    manifest: ConnectorManifest,
    key: str,
    *,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[Any]:
    info = manifest.info
    ctx = context or {}

    if key in {"env", "environment"}:
        return info.env.value
    if key == "domain":
        return info.domain
    if key in {"type", "connector_type", "ctype"}:
        return info.connector_type.value
    if key == "system":
        return info.system
    if key in {"connector_dir", "dir"}:
        return info.connector_dir
    if key in {"connector", "name"}:
        return manifest.name
    if key in {"kind", "subtype"}:
        if info.connector_type != ConnectorType.sink:
            return None
        return info.variant or "default"
    if key in {"cluster", "cluster_group"}:
        return ctx.get("cluster_group") or ctx.get("cluster")
    if key in {"tag", "tags"}:
        tags = ctx.get("tags")
        if tags is None:
            return None
        return [str(t) for t in _as_list(tags) if str(t)]

    return None


def _applies_to(
    manifest: ConnectorManifest,
    applies_to: Dict[str, Any],
    *,
    context: Optional[Dict[str, Any]] = None,
) -> bool:
    if not applies_to:
        return True

    for k, wanted in applies_to.items():
        negative = False
        selector_key = k
        if k.startswith("not_"):
            negative = True
            selector_key = k[4:]
        elif k.startswith("exclude_"):
            negative = True
            selector_key = k[8:]

        v = _selector_value(manifest, selector_key, context=context)
        if negative and v is None:
            continue
        if v is None:
            return False
        wanted_list = [str(x) for x in _as_list(wanted)]
        if isinstance(v, (list, tuple, set)):
            values = [str(x) for x in v]
            matched = bool(wanted_list) and any(
                _match_any(val, wanted_list) for val in values
            )
            if negative:
                if matched:
                    return False
                continue
            if wanted_list and not matched:
                return False
        else:
            matched = bool(wanted_list) and _match_any(str(v), wanted_list)
            if negative:
                if matched:
                    return False
                continue
            if wanted_list and not matched:
                return False
    return True
