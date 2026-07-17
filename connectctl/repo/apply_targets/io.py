from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from ...models import Environment
from ...ports import FileSystem


def load_yaml_or_json(path: Path, *, fs: FileSystem | None = None) -> Any:
    raw = (
        fs.read_text(path, encoding="utf-8") if fs else path.read_text(encoding="utf-8")
    )
    if not raw.strip():
        return None
    # YAML loader can read JSON too.
    return yaml.safe_load(raw)


def load_vars_from_env_file(
    env_file: Path, *, fs: FileSystem | None = None
) -> Dict[str, Any]:
    try:
        obj = load_yaml_or_json(env_file, fs=fs)
    except Exception:
        return {}
    if not isinstance(obj, dict):
        return {}
    vars_obj = obj.get("vars") or {}
    return vars_obj if isinstance(vars_obj, dict) else {}


def find_nearest_env_file(
    start_dir: Path,
    env: Environment,
    repo_root: Path,
    *,
    fs: FileSystem | None = None,
) -> Optional[Path]:
    cur = start_dir.resolve()
    repo_root = repo_root.resolve()
    while True:
        for name in (f"{env.value}.json", f"{env.value}.yaml", f"{env.value}.yml"):
            cand = cur / name
            if fs:
                if fs.exists(cand) and fs.is_file(cand):
                    return cand
            else:
                if cand.exists() and cand.is_file():
                    return cand
        if cur == repo_root:
            return None
        if cur.parent == cur:
            return None
        cur = cur.parent
