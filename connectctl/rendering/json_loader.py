from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from ..exceptions import RenderError
from ..ports import FileSystem

from ..utils import expand_env_in_obj
from .unset_config import (
    BKKT_META_KEY,
    LEGACY_DOTTED_UNSET_CONFIG_KEYS_KEY,
    extract_bkkt_meta,
)


def load_json_file(path: Path, *, fs: FileSystem | None = None) -> Any:
    """Load JSON file. Empty file => {}"""
    raw = (
        fs.read_text(path, encoding="utf-8") if fs else path.read_text(encoding="utf-8")
    ).strip()
    if not raw:
        return {}
    try:
        return expand_env_in_obj(json.loads(raw))
    except json.JSONDecodeError as e:
        raise RenderError(f"Invalid JSON in {path}: {e}") from e


def normalize_fragment(obj: Any) -> Dict[str, Any]:
    """Normalize JSON content into a fragment with optional 'name', 'config', 'vars'.

    Supported shapes:

    A) Full manifest (common for env-specific files):
       {"name": "...", "config": {...}}

    B) Wrapper fragment:
       {"config": {...}} or {"name": "..."} or {"vars": {...}} or {"connectctl": {...}}

    C) Flat config fragment (common for overrides and base files in your repo):
       {
         "name": "${...}",   # optional
         "vars": {...},       # optional
         "connectctl": {...}, # optional (tool metadata, not sent to Kafka Connect)
         "tags": [...],       # optional shorthand for connectctl.tags
         "transforms": "...",
         "errors.tolerance": "all",
         ...
       }
       => treated as:
          {"name": <name?>, "vars": <vars?>, "connectctl": <meta?>, "config": <all other keys>}
    """
    if obj is None:
        return {}

    if not isinstance(obj, Mapping):
        raise RenderError(f"Expected JSON object/dict, got: {type(obj).__name__}")

    def _normalize_tags(val: Any) -> Optional[Sequence[str]]:
        if val is None:
            return None
        if isinstance(val, str):
            v = val.strip()
            return [v] if v else []
        if isinstance(val, (list, tuple)):
            out = []
            for x in val:
                s = str(x).strip()
                if s:
                    out.append(s)
            return out
        raise RenderError("'tags' must be a string or list")

    # If explicit 'config' exists, treat it as wrapper manifest/fragment.
    if "config" in obj:
        frag: Dict[str, Any] = {}
        if "name" in obj and obj["name"] is not None:
            frag["name"] = obj["name"]
        if obj["config"] is not None:
            if not isinstance(obj["config"], Mapping):
                raise RenderError("'config' must be an object/dict")
            frag["config"] = dict(obj["config"])
        if "vars" in obj and obj["vars"] is not None:
            if not isinstance(obj["vars"], Mapping):
                raise RenderError("'vars' must be an object/dict")
            frag["vars"] = dict(obj["vars"])
        bkkt_meta = extract_bkkt_meta(obj)
        if bkkt_meta:
            frag[BKKT_META_KEY] = bkkt_meta

        # Tool metadata (not sent to Kafka Connect)
        cc: Dict[str, Any] = {}
        if "connectctl" in obj and obj["connectctl"] is not None:
            if not isinstance(obj["connectctl"], Mapping):
                raise RenderError("'connectctl' must be an object/dict")
            cc.update(dict(obj["connectctl"]))
        if "tags" in obj and obj["tags"] is not None:
            tags = _normalize_tags(obj["tags"])
            if tags is not None:
                cc["tags"] = list(tags)
        if cc:
            frag["connectctl"] = cc
        return frag

    # Otherwise, treat as flat fragment:
    frag = {}
    config_obj = dict(obj)

    if "name" in config_obj:
        frag["name"] = config_obj.pop("name")
    if "vars" in config_obj:
        vars_val = config_obj.pop("vars")
        if vars_val is not None:
            if not isinstance(vars_val, Mapping):
                raise RenderError("'vars' must be an object/dict")
            frag["vars"] = dict(vars_val)

    bkkt_source: Dict[str, Any] = {}
    if BKKT_META_KEY in config_obj:
        bkkt_source[BKKT_META_KEY] = config_obj.pop(BKKT_META_KEY)
    if LEGACY_DOTTED_UNSET_CONFIG_KEYS_KEY in config_obj:
        bkkt_source[LEGACY_DOTTED_UNSET_CONFIG_KEYS_KEY] = config_obj.pop(
            LEGACY_DOTTED_UNSET_CONFIG_KEYS_KEY
        )
    bkkt_meta = extract_bkkt_meta(bkkt_source)
    if bkkt_meta:
        frag[BKKT_META_KEY] = bkkt_meta

    # Tool metadata (not sent to Kafka Connect)
    if "connectctl" in config_obj:
        cc_val = config_obj.pop("connectctl")
        if cc_val is not None:
            if not isinstance(cc_val, Mapping):
                raise RenderError("'connectctl' must be an object/dict")
            frag["connectctl"] = dict(cc_val)
    if "tags" in config_obj:
        tags_val = config_obj.pop("tags")
        if tags_val is not None:
            tags = _normalize_tags(tags_val)
            if tags is not None:
                frag.setdefault("connectctl", {})
                frag["connectctl"]["tags"] = list(tags)

    # Export annotations are comments, not Kafka Connect config.
    config_obj.pop("__export_comments__", None)

    # Remaining keys are config entries
    if config_obj:
        frag["config"] = config_obj

    return frag
