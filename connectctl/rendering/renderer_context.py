from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple

from ..models import ConnectorPathInfo
from ..utils import flatten_dict
from .renderer_infer import (
    infer_dataset_from_connector_dir,
    infer_dataset_from_name,
    infer_index_from_name,
)


def build_meta_context(
    info: ConnectorPathInfo,
    *,
    name: str,
    extra_meta: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build metadata placeholder context (env/domain/type/system/etc.)."""

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

    # Derived convenience vars
    if info.connector_type.value == "sink":
        sink_kind = info.variant or "default"
        meta_ctx["sink"] = {
            "kind": sink_kind,
            # Used by SetTableNameToRouteField templates; these kinds typically have no suffix.
            "table_suffix": "" if sink_kind in {"default", "raw", "ods"} else sink_kind,
        }

    if extra_meta:
        meta_ctx.update(dict(extra_meta))

    return meta_ctx


def build_flat_placeholder_context(
    info: ConnectorPathInfo,
    *,
    name: str,
    vars_ctx: Mapping[str, Any],
    vars_sources: Dict[str, str],
    extra_meta: Optional[Mapping[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, str]]:
    """Build the flattened placeholder context.

    Returns:
        ctx_flat: merged map of meta + vars (flattened)
        meta_flat: flattened meta-only map (for provenance)
        vars_sources: updated sources map (dataset/index auto-inference)
    """

    meta_ctx = build_meta_context(info, name=name, extra_meta=extra_meta)

    meta_flat = flatten_dict(meta_ctx)
    ctx_flat: Dict[str, Any] = dict(meta_flat)

    vars_flat = flatten_dict(dict(vars_ctx))

    # Auto-infer dataset/index if missing.
    if "dataset" not in vars_flat:
        ds_from_name = infer_dataset_from_name(name, info.env.value)
        ds = ds_from_name or infer_dataset_from_connector_dir(info.connector_dir)
        if ds:
            vars_flat["dataset"] = ds
            vars_sources.setdefault(
                "dataset",
                "auto:connector_name" if ds_from_name else "auto:connector_dir",
            )

    if "index" not in vars_flat:
        idx = infer_index_from_name(name)
        if idx:
            vars_flat["index"] = idx
            vars_sources.setdefault("index", "auto:requested_filename")

    ctx_flat.update(vars_flat)
    return ctx_flat, meta_flat, vars_sources
