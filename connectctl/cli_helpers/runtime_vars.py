"""Runtime vars helpers (CLI).

This module is kept as a facade for backwards compatibility.
The implementation is split into small SRP-friendly modules.
"""

from __future__ import annotations

from .runtime_vars_load import (
    _load_runtime_vars,
    _load_runtime_vars_with_sources,
    _print_vars_used,
)
from .runtime_vars_parse import _parse_vars_arg
from .runtime_vars_files import _parse_vars_file_args

__all__ = [
    "_parse_vars_arg",
    "_parse_vars_file_args",
    "_load_runtime_vars",
    "_load_runtime_vars_with_sources",
    "_print_vars_used",
]
