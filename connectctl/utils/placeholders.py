from __future__ import annotations

# Backwards-compatible facade:
# Historically code imported:
#   from connectctl.utils.placeholders import resolve_placeholders, flatten_dict, PlaceholderTrace
#
# Реальная логика разнесена по небольшим модулям.

from .placeholders_flatten import flatten_dict
from .placeholders_models import PlaceholderTrace, PlaceholderUse
from .placeholders_resolver import resolve_placeholders

__all__ = [
    "flatten_dict",
    "resolve_placeholders",
    "PlaceholderTrace",
    "PlaceholderUse",
]
