from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ..exceptions import ConfigError
from ..ports import FileSystem
from ..rendering.config_merge import merge_config_with_deletes
from ..rendering.json_loader import normalize_fragment
from ..rendering.unset_config import (
    BKKT_META_KEY,
    UNSET_CONFIG_KEYS_KEY,
    apply_unset_config_keys,
    normalize_unset_config_keys,
)
from ..utils import deep_merge
from .virtual_io import load_json_virtual


def collect_fragments(
    *,
    layers: Sequence[Path],
    planned_files: Mapping[Path, Any],
    track_sources: bool,
    fs: FileSystem | None = None,
) -> Tuple[Optional[str], Dict[str, Any], Dict[str, Any], Dict[str, Path]]:
    name: Optional[str] = None
    config: Dict[str, Any] = {}
    vars_ctx: Dict[str, Any] = {}
    key_sources: Dict[str, Path] = {}

    for lp in layers:
        obj = load_json_virtual(lp, planned_files, fs=fs)
        frag = normalize_fragment(obj)

        if "vars" in frag and frag["vars"] is not None:
            if not isinstance(frag["vars"], Mapping):
                raise ConfigError(f"vars must be an object in {lp}")
            vars_ctx = deep_merge(vars_ctx, dict(frag["vars"]))

        if "name" in frag and frag["name"]:
            name = str(frag["name"])

        if "config" in frag and frag["config"] is not None and frag["config"]:
            if not isinstance(frag["config"], Mapping):
                raise ConfigError(f"config must be an object in {lp}")
            cfg_part = dict(frag["config"])
            if track_sources:
                for k, v in cfg_part.items():
                    if v is None:
                        key_sources.pop(str(k), None)
                        continue
                    key_sources[str(k)] = lp
            config = merge_config_with_deletes(config, cfg_part)

        if BKKT_META_KEY in frag and frag[BKKT_META_KEY] is not None:
            if not isinstance(frag[BKKT_META_KEY], Mapping):
                raise ConfigError(f"bkkt must be an object in {lp}")
            unset_keys = normalize_unset_config_keys(
                dict(frag[BKKT_META_KEY]).get(UNSET_CONFIG_KEYS_KEY),
                source=f"bkkt.{UNSET_CONFIG_KEYS_KEY}:{lp}",
            )
            if unset_keys:
                config = apply_unset_config_keys(config, unset_keys)
                if track_sources:
                    for key in unset_keys:
                        key_sources.pop(key, None)

    return name, config, vars_ctx, key_sources
