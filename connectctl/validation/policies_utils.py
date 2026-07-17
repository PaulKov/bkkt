from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Tuple

from .policies_models import PolicyIssue


def load_json_no_env(path: Path) -> Any:
    """Load JSON без expand ${ENV} плейсхолдеров.

    NOTE: connectctl.rendering.json_loader.load_json_file делает expand env vars.
    Для policy lint нам нужен *оригинальный* контент файла.
    """
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    return json.loads(raw)


def iter_strings_in_mapping(obj: Mapping[str, Any]) -> Iterable[Tuple[str, str]]:
    """Yield (key, value) for string values in a flat mapping."""
    for k, v in obj.items():
        if isinstance(v, str):
            yield str(k), v


def dedupe(issues: List[PolicyIssue]) -> List[PolicyIssue]:
    seen: set[tuple] = set()
    out: List[PolicyIssue] = []
    for i in issues:
        key = (i.policy, i.severity, i.manifest_path, i.file_path, i.key, i.message)
        if key in seen:
            continue
        seen.add(key)
        out.append(i)
    return out
