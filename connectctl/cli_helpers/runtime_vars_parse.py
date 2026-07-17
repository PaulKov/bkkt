from __future__ import annotations

import json
from typing import List, Optional

from ..exceptions import ConfigError
from ..utils import deep_merge


def _parse_vars_arg(vars_list: Optional[List[str]]) -> dict:
    """Parse dbt-style --vars JSON strings into a single dict.

    Multiple --vars are merged (later wins for scalar keys; dicts deep-merged).
    Example:
      --vars '{"iceberg": {"db_name": "..."}}'
    """

    merged: dict = {}
    if not vars_list:
        return merged
    for raw in vars_list:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ConfigError(
                f"--vars must be a valid JSON object, got: {raw!r}"
            ) from e
        if not isinstance(obj, dict):
            raise ConfigError(
                f"--vars must be a JSON object (mapping), got {type(obj).__name__}"
            )
        merged = deep_merge(merged, obj)
    return merged
