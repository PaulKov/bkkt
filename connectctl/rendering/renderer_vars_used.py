from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from ..utils.placeholders import PlaceholderTrace
from .renderer_models import VarUsage
from .renderer_sensitive import is_sensitive_var


def build_vars_used(
    trace: PlaceholderTrace,
    *,
    ctx_flat: Mapping[str, Any],
    meta_flat: Mapping[str, Any],
    vars_sources: Mapping[str, str],
) -> Tuple[VarUsage, ...]:
    """Build vars-used report (only vars actually substituted).

    - Sensitive keys are masked.
    - Uses provenance from `vars_sources` when available.
    """

    used: Dict[str, VarUsage] = {}

    for use in trace.uses:
        key = use.key
        if not key or ":" in key:
            continue

        if use.source in ("os_env", "default"):
            val = use.value if use.value is not None else ""
            src = use.source
        elif use.source == "unresolved":
            val = ""
            src = "unresolved"
        else:
            val = str(ctx_flat.get(key, ""))
            src = vars_sources.get(key) or ("meta" if key in meta_flat else use.source)

        if is_sensitive_var(key):
            val = "***"
        used[key] = VarUsage(key=key, value=val, source=src)

    return tuple(used[k] for k in sorted(used.keys()))
