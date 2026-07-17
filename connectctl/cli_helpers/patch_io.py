"""Helpers for reading raw connector configs and patch payloads.

This module used to be a single ~250 LOC implementation.
Refactor stage 25 split it into focused helpers:

  - patch_io_files.py
  - patch_io_json.py
  - patch_io_kv.py
  - patch_io_payload.py
  - patch_io_split.py

The original public helper names are re-exported for backwards compatibility.
"""

from __future__ import annotations

from .patch_io_files import _read_text_file_or_dash
from .patch_io_json import (
    _extract_name_and_config,
    _read_json_mapping_from_text,
    _read_raw_json,
)
from .patch_io_kv import _coerce_connect_config_values, _parse_kv_pairs, _parse_kv_text
from .patch_io_payload import _read_patch_payload
from .patch_io_split import _split_patch_set_and_delete

__all__ = [
    "_coerce_connect_config_values",
    "_extract_name_and_config",
    "_parse_kv_pairs",
    "_parse_kv_text",
    "_read_json_mapping_from_text",
    "_read_patch_payload",
    "_read_raw_json",
    "_read_text_file_or_dash",
    "_split_patch_set_and_delete",
]
