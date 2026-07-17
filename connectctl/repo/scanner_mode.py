from __future__ import annotations

import re
from typing import Callable, Optional

from ..models import ConnectorType

# Built-in modes + aliases.
# NOTE: values are canonical ("init"/"cdc").
_MODE_ALIASES = {
    "initial": "init",
    "stream": "cdc",
}


def _canonical_mode(token: str) -> Optional[str]:
    t = str(token or "").strip().lower()
    if not t:
        return None
    if t in {"init", "cdc"}:
        return t
    return _MODE_ALIASES.get(t)


def guess_mode(
    connector_dir: str,
    remainder_noext: Optional[str] = None,
    *,
    connector_type: Optional[ConnectorType] = None,
    mode_exists: Callable[[str], bool] | None = None,
) -> Optional[str]:
    """Best-effort inference of connector mode.

    Mode is primarily used for selecting additional override layers:

      .../modes/<mode>/all.json
      .../modes/<mode>/<env>.json

    Precedence (more specific wins):
      1) dot-style connector *name* / filename tokens (source only)
      2) connector_dir tokens

    Built-in modes:
      - init (aliases: initial)
      - cdc  (aliases: stream)

    Custom modes are supported **only when we can confirm they exist** in the repo
    (via ``mode_exists`` callback). This prevents false positives for tokens like
    'dbt' that might appear in names but are not modes.
    """

    if connector_type is not None and connector_type != ConnectorType.source:
        return None

    # 1) Most specific: infer from dot-style name / filename tokens.
    if remainder_noext:
        parts = [p.strip().lower() for p in remainder_noext.split(".") if p.strip()]

        tail = parts
        if "source" in parts:
            i = parts.index("source")
            # tokens after `source.<system>.` (if present)
            if len(parts) >= i + 2:
                tail = parts[i + 2 :]

        # Built-ins first.
        for tok in tail:
            canon = _canonical_mode(tok)
            if canon:
                return canon

        # Custom mode: only if we know such mode overlays exist in the repo.
        if mode_exists is not None:
            for tok in tail:
                t = str(tok or "").strip().lower()
                if not t or t.isdigit():
                    continue
                if mode_exists(t):
                    return t

    # 2) Fallback: infer from connector_dir tokens.
    d = (connector_dir or "").lower()

    # Built-ins (best-effort): treat '-init'/'_init'/'__init' as initial-load;
    # '-cdc'/'_cdc'/'__cdc' as cdc/streaming.
    if re.search(r"(^|[-_])init($|[-_])", d) or "initial" in d:
        return "init"
    if re.search(r"(^|[-_])cdc($|[-_])", d) or "stream" in d:
        return "cdc"

    # Custom mode in connector_dir: prefer explicit token separators (double-underscore, dash, underscore).
    if mode_exists is not None:
        # Common convention: connector_<domain>__<dataset>__<suffix1>__<suffix2>
        # We try to ignore the first two segments (connector_<domain>, dataset) when present.
        segments = [s for s in re.split(r"__+", d) if s]
        if segments and segments[0].startswith("connector_") and len(segments) >= 3:
            segments = segments[2:]

        candidates: list[str] = []
        for seg in segments:
            # split combined seg further by '-'/'_' to catch patterns like 'foo-backfill'
            for t in re.split(r"[-_]+", seg):
                tt = t.strip().lower()
                if tt:
                    candidates.append(tt)

        for tok in candidates:
            if mode_exists(tok):
                return tok

    return None
