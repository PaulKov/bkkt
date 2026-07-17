from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence


def _json_text_for_regex(name: str, config: Mapping[str, Any]) -> str:
    try:
        cfg_txt = json.dumps(config, ensure_ascii=False, sort_keys=True)
    except Exception:
        cfg_txt = str(config)
    return name + "\n" + cfg_txt


def matches_any_regexp(
    *,
    name: str,
    config: Mapping[str, Any],
    patterns: Sequence[re.Pattern[str]],
) -> bool:
    """Match a connector by name and config JSON.

    The regexp list is applied to a concatenation of name + '\n' + json(config).
    When no patterns are provided, the connector is considered a match.

    This helper exists mainly to implement `connectctl export --grep/--regexp`.
    """
    if not patterns:
        return True
    text = _json_text_for_regex(name, config)
    return any(p.search(text) for p in patterns)
