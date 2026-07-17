from __future__ import annotations

import json
from typing import Any, Dict, Mapping

from ..exceptions import ConfigError


_PATCH_DELETE_TOKENS = {"__DELETE__", "__REMOVE__", "__UNSET__"}


def _kv_error_hint(value: str) -> str:
    return (
        f"Invalid key=value entry: {value!r} (expected k=v). "
        "If the value contains commas, pass it as one literal: "
        "--set 'table.include.list=a,b,c'. For complex patches prefer "
        '--json-file patch.json or --json \'{"key":"value"}\'.'
    )


def _parse_kv_literal(raw: str) -> Dict[str, str]:
    """Parse one literal `k=v` entry.

    Unlike legacy CSV parsing, commas inside the value are preserved. Kafka
    Connect configs frequently use comma-separated values (for example
    `table.include.list`), so this is the safe default for `bkkt connect patch
    --set`.
    """

    part = (raw or "").strip()
    if not part:
        return {}
    if "=" not in part:
        raise ConfigError(_kv_error_hint(part))
    k, v = part.split("=", 1)
    k = k.strip()
    if not k:
        raise ConfigError(f"Invalid key=value entry: {part!r} (empty key)")
    return {k: v.strip()}


def _parse_kv_pairs(raw: str) -> Dict[str, str]:
    """Parse a legacy comma-separated `k=v` list."""

    out: Dict[str, str] = {}
    s = (raw or "").strip()
    if not s:
        return out

    parts = [p.strip() for p in s.split(",") if p.strip()]
    for part in parts:
        if "=" not in part:
            raise ConfigError(_kv_error_hint(part))
        k, v = part.split("=", 1)
        k = k.strip()
        if not k:
            raise ConfigError(f"Invalid key=value entry: {part!r} (empty key)")
        out[k] = v.strip()
    return out


def _parse_kv_text(text: str) -> Dict[str, str]:
    """Parse key=value config from a text blob.

    Supports:
      - one literal `k=v` per line
      - ignores blank lines and lines starting with `#`
    """

    out: Dict[str, str] = {}
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            out.update(_parse_kv_literal(line))
        except ConfigError as exc:
            raise ConfigError(f"Invalid key=value line: {raw_line!r}. {exc}") from exc
    return out


def _coerce_connect_config_values(cfg: Mapping[str, Any]) -> Dict[str, str]:
    """Kafka Connect configs are a string map; coerce values to strings.

    - dict/list are JSON-encoded
    - None becomes empty string
    """

    out: Dict[str, str] = {}
    for k, v in (cfg or {}).items():
        if v is None:
            out[str(k)] = ""
        elif isinstance(v, (dict, list)):
            out[str(k)] = json.dumps(v, ensure_ascii=False)
        else:
            out[str(k)] = str(v)
    return out


__all__ = [
    "_PATCH_DELETE_TOKENS",
    "_parse_kv_literal",
    "_parse_kv_pairs",
    "_parse_kv_text",
    "_coerce_connect_config_values",
]
