from __future__ import annotations

import argparse
import sys
from typing import Any, Dict

from ..exceptions import ConfigError
from .patch_io_files import _read_text_file_or_dash
from .patch_io_json import _read_json_mapping_from_text
from .patch_io_kv import _parse_kv_literal, _parse_kv_pairs, _parse_kv_text


def _read_patch_payload(args: argparse.Namespace) -> Dict[str, Any]:
    """Read a partial config patch from CLI flags / files / stdin.

    Supported sources (can be combined, later sources override earlier ones):
      - --json '{...}'
      - --json-file path.json
      - --set k=v (literal; commas in value are preserved)
      - --set-csv k=v,k2=v2 (legacy comma-separated pairs)
      - --set-file path.properties (one literal k=v per line)
      - --stdin (JSON or key=value)

    If none of the sources are provided, we read from stdin by default (auto-detect).
    """

    merged: Dict[str, Any] = {}

    # 1) JSON files
    for jf in getattr(args, "json_file", None) or []:
        txt = _read_text_file_or_dash(str(jf))
        obj = _read_json_mapping_from_text(txt, src_label=f"--json-file {jf}")
        merged.update(obj)

    # 2) JSON inline
    for js in getattr(args, "json", None) or []:
        obj = _read_json_mapping_from_text(str(js), src_label="--json")
        merged.update(obj)

    # 3) key=value files
    for sf in getattr(args, "set_file", None) or []:
        txt = _read_text_file_or_dash(str(sf))
        merged.update(_parse_kv_text(txt))

    # 4) key=value inline, literal-safe by default
    for s in getattr(args, "set", None) or []:
        merged.update(_parse_kv_literal(str(s)))

    # 5) legacy comma-separated key=value inline
    for s in getattr(args, "set_csv", None) or []:
        merged.update(_parse_kv_pairs(str(s)))

    # 6) stdin (optional or default)
    stdin_flag = bool(getattr(args, "stdin", False))
    if stdin_flag or not merged:
        if sys.stdin.isatty():
            if not merged:
                raise ConfigError(
                    "Patch payload is required. Provide --json/--set/--json-file/--set-file or pipe stdin."
                )
        else:
            raw = sys.stdin.read()
            if (raw or "").strip():
                raw_stripped = raw.strip()
                if raw_stripped.startswith("{"):
                    obj = _read_json_mapping_from_text(raw_stripped, src_label="stdin")
                    merged.update(obj)
                else:
                    merged.update(_parse_kv_text(raw))
            elif not merged:
                raise ConfigError("Patch payload is empty (stdin is empty)")

    if not merged:
        raise ConfigError("Patch payload is empty")

    return merged


__all__ = ["_read_patch_payload"]
