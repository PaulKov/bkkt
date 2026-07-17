"""
Backwards-compatible facade for CLI helper functions.

Refactor stage 4:
- `cli_support.py` used to be a large god-module.
- The implementation was split into small modules under `connectctl.cli.*`.
- This file re-exports the old helper names so existing code keeps working.
"""

from __future__ import annotations

from .cli_helpers.config import (
    DEFAULT_CONFIG_PATHS,
    _build_renderer,
    _find_config_path,
    _print_cluster_banner,
    _resolve_cluster_from_args,
    _validate_manifest,
)
from .cli_helpers.git_changes import _expand_renames, _render_for_deleted_path
from .cli_helpers.patch_io import (
    _coerce_connect_config_values,
    _extract_name_and_config,
    _parse_kv_pairs,
    _parse_kv_text,
    _read_json_mapping_from_text,
    _read_patch_payload,
    _read_raw_json,
    _read_text_file_or_dash,
    _split_patch_set_and_delete,
)
from .cli_helpers.runtime_vars import (
    _load_runtime_vars,
    _load_runtime_vars_with_sources,
    _parse_vars_arg,
    _parse_vars_file_args,
    _print_vars_used,
)
from .cli_helpers.selectors import (
    _compile_name_regexps,
    _select_connectors,
    _split_names_csv,
)
from .cli_helpers.templates import _print_template_expansions

__all__: list[str] = [
    "DEFAULT_CONFIG_PATHS",
    "_build_renderer",
    "_find_config_path",
    "_print_cluster_banner",
    "_resolve_cluster_from_args",
    "_validate_manifest",
    "_expand_renames",
    "_render_for_deleted_path",
    "_coerce_connect_config_values",
    "_extract_name_and_config",
    "_parse_kv_pairs",
    "_parse_kv_text",
    "_read_json_mapping_from_text",
    "_read_patch_payload",
    "_read_raw_json",
    "_read_text_file_or_dash",
    "_split_patch_set_and_delete",
    "_load_runtime_vars",
    "_load_runtime_vars_with_sources",
    "_parse_vars_arg",
    "_parse_vars_file_args",
    "_print_vars_used",
    "_compile_name_regexps",
    "_select_connectors",
    "_split_names_csv",
    "_print_template_expansions",
]
