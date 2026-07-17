from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..exceptions import ConfigError


def _read_raw_json(path_or_dash: str) -> Any:
    """Load JSON from a file path or '-' (stdin)."""

    src = (path_or_dash or "-").strip()
    if src == "-":
        if sys.stdin.isatty():
            raise ConfigError(
                "Expected JSON via stdin (use a pipe) or provide a JSON file path"
            )
        raw = sys.stdin.read()
        if not (raw or "").strip():
            raise ConfigError("Got empty stdin JSON")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ConfigError("stdin must be valid JSON") from e

    p = Path(src)
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    if not p.exists():
        raise ConfigError(f"JSON file not found: {p}")
    raw = p.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"{p} must be valid JSON") from e


def _read_json_mapping_from_text(text: str, *, src_label: str) -> Dict[str, Any]:
    """Parse a JSON text blob and ensure it's a JSON object (mapping)."""

    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfigError(f"{src_label} must be a valid JSON object") from e
    if not isinstance(obj, dict):
        raise ConfigError(
            f"{src_label} must be a JSON object (mapping), got {type(obj).__name__}"
        )
    return dict(obj)


def _extract_name_and_config(
    raw_obj: Any, explicit_name: Optional[str]
) -> Tuple[str, Dict[str, Any]]:
    """Extract (name, config) from either full payload or config-only JSON."""

    if not isinstance(raw_obj, dict):
        raise ConfigError(f"Expected JSON object, got: {type(raw_obj).__name__}")

    name = (explicit_name or "").strip()

    # Support both formats:
    # 1) full payload: {"name": "...", "config": {...}}
    # 2) config map only: {...} (requires --name)
    if "config" in raw_obj and isinstance(raw_obj.get("config"), dict):
        if not name:
            name = str(raw_obj.get("name") or "").strip()
        cfg = raw_obj.get("config") or {}
        if not isinstance(cfg, dict):
            raise ConfigError("'config' must be an object")
        if not name:
            raise ConfigError(
                "Connector name is required (provide --name or include 'name' in JSON payload)"
            )
        return name, dict(cfg)

    # Config-only
    if not name:
        raise ConfigError(
            "Connector name is required for config-only JSON (provide --name)"
        )
    return name, dict(raw_obj)
