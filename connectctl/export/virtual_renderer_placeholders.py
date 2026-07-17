from __future__ import annotations

from typing import Any, Dict, Tuple

from ..utils import flatten_dict, resolve_placeholders


def resolve_placeholders_for_render(
    *,
    info: Any,
    name: str,
    config: Dict[str, Any],
    vars_ctx: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    meta_ctx: Dict[str, Any] = {
        "env": info.env.value,
        "domain": info.domain,
        "type": info.connector_type.value,
        "system": info.system,
        "connector_dir": info.connector_dir,
        "connector_file": str(info.relpath),
        "connector": {"name": name},
        "global": {"connector": {"name": name}},
    }
    if info.connector_type.value == "sink":
        sink_kind = info.variant or "default"
        meta_ctx["sink"] = {
            "kind": sink_kind,
            "table_suffix": "" if sink_kind == "default" else sink_kind,
        }

    ctx_flat: Dict[str, Any] = {}
    ctx_flat.update(flatten_dict(meta_ctx))
    ctx_flat.update(flatten_dict(vars_ctx))

    resolved_name = resolve_placeholders(name, ctx_flat)
    resolved_config = resolve_placeholders(config, ctx_flat)

    return str(resolved_name), dict(resolved_config)
