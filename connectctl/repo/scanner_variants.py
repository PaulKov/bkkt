from __future__ import annotations

import re
from typing import Optional

from ..models import RepoConfig
from ..ports import FileSystem


_RESERVED_AFTER_CDC = {"dbt"}


def _sink_kind_exists(
    *,
    cfg: RepoConfig,
    fs: FileSystem | None,
    domain: str,
    system: str,
    connector_dir: str,
    kind: str,
) -> bool:
    cand = str(kind or "").strip().lower()
    if not cand:
        return False

    kind_paths = [
        cfg.connectors_root
        / domain
        / "sink"
        / system
        / connector_dir
        / "types"
        / cand
        / "all.json",
        cfg.connectors_root / domain / "sink" / system / "types" / cand / "all.json",
        cfg.root / "__global" / "sink" / system / "types" / cand / "all.json",
    ]
    return any((fs.exists(p) if fs else p.exists()) for p in kind_paths)


def infer_sink_variant(
    *,
    cfg: RepoConfig,
    fs: FileSystem | None = None,
    domain: str,
    system: str,
    connector_dir: str,
    remainder_noext: str,
    underscore_style: bool,
) -> Optional[str]:
    """Infer sink variant/kind (events/flatten/custom) from manifest file name.

    Логика перенесена из ConnectorRepo.parse_connector_path для улучшения
    читаемости, поведение оставлено без изменений.
    """
    variant: Optional[str] = None

    if underscore_style:
        # underscore-style: <env>_sink_<layer>_<...>__(<kind>)?.json
        tokens = [t for t in remainder_noext.split("__") if t]
        if len(tokens) >= 3:
            cand = tokens[-1]
            # Only treat last token as a sink kind if there is a corresponding
            # types/<kind>/ override layer. This avoids mis-detecting connector
            # "variants" (e.g. __common_tables) as kinds.
            if _sink_kind_exists(
                cfg=cfg,
                fs=fs,
                domain=domain,
                system=system,
                connector_dir=connector_dir,
                kind=cand,
            ):
                variant = cand

        # If no explicit kind suffix detected, infer kind from sink layer when it is a known one.
        if variant is None:
            m_layer = re.match(
                r"^sink[_-](raw|ods)[_-]", remainder_noext, re.IGNORECASE
            )
            if m_layer:
                variant = m_layer.group(1).lower()
        return variant

    # dot-style: <env>.<...>.sink.<layer>.<system>.(cdc.)?(<kind>.)?.<index>.json
    parts_name = remainder_noext.split(".")
    has_cdc = "cdc" in parts_name

    # For CDC sinks, kind is the segment after `cdc` (events/flatten/custom).
    # Reserved tokens (e.g. "dbt") are NOT kinds.
    if has_cdc:
        i = parts_name.index("cdc")
        if i + 1 < len(parts_name):
            cand = parts_name[i + 1]
            if cand and not cand.isdigit() and cand not in _RESERVED_AFTER_CDC:
                variant = cand

    # For non-CDC sinks, treat sink layer (raw/ods) as kind when it is known.
    if variant is None and not has_cdc:
        tail_tokens = [p for p in parts_name[5:-1] if p]
        for cand in reversed(tail_tokens):
            if _sink_kind_exists(
                cfg=cfg,
                fs=fs,
                domain=domain,
                system=system,
                connector_dir=connector_dir,
                kind=cand,
            ):
                variant = cand
                break

    # For non-CDC sinks without an explicit kind overlay, fall back to sink layer.
    if variant is None and not has_cdc:
        if len(parts_name) >= 5 and parts_name[2].lower() == "sink":
            layer_tok = parts_name[3].lower()
            if layer_tok in {"raw", "ods"}:
                variant = layer_tok
    return variant
