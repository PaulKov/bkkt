from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List

from ..exceptions import RenderError
from ..git import show_file_at
from ..settings import Settings


def _expand_renames(changes: Iterable[Any]) -> List[Any]:
    """Expand git rename entries (Rxxx) into a delete + add pair."""
    expanded: List[Any] = []
    for ch in changes:
        if (
            str(getattr(ch, "status", "")).startswith("R")
            and getattr(ch, "old_path", None) is not None
        ):
            expanded.append(type(ch)(status="D", path=ch.old_path))
            expanded.append(type(ch)(status="A", path=ch.path))
        else:
            expanded.append(ch)
    return expanded


def _render_for_deleted_path(
    *,
    repo_root: Path,
    base_ref: str,
    relpath: Path,
    settings: Settings,
) -> str:
    """Render connector name for a deleted manifest path using git show base_ref:path.

    For deletions we usually only need the connector name, so we parse the JSON content directly.
    If you use layering/templating for the 'name' field (not recommended for env-specific manifests),
    you may need to extend this to render using historic overrides too.
    """
    raw = show_file_at(base_ref, relpath, repo_root=repo_root).strip()
    if not raw:
        raise RenderError(f"Deleted file {relpath} at {base_ref} is empty")
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RenderError(f"Invalid JSON in deleted file {relpath}: {e}") from e
    if isinstance(obj, dict) and obj.get("name"):
        return str(obj["name"])
    raise RenderError(f"Deleted manifest {relpath} does not contain 'name' field")
