from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ...models import Environment
from ...ports import FileSystem

from .io import find_nearest_env_file, load_vars_from_env_file, load_yaml_or_json


def load_instances_from_file(
    path: Path, *, fs: FileSystem | None = None
) -> List[Dict[str, str]]:
    obj = load_yaml_or_json(path, fs=fs)
    if obj is None:
        return []
    if isinstance(obj, dict):
        obj = obj.get("instances")
    if not isinstance(obj, list):
        return []
    out: List[Dict[str, str]] = []
    for it in obj:
        if not isinstance(it, dict):
            continue
        out.append({str(k): str(v) for k, v in it.items()})
    return out


def load_instances_from_vars(vars_obj: Dict[str, Any]) -> List[Dict[str, str]]:
    inst = vars_obj.get("instances")
    if isinstance(inst, list):
        out: List[Dict[str, str]] = []
        for it in inst:
            if not isinstance(it, dict):
                continue
            out.append({str(k): str(v) for k, v in it.items()})
        return out
    idx = vars_obj.get("index")
    if isinstance(idx, list):
        return [{"index": str(v)} for v in idx]
    return []


def load_instances(
    connector_dir: Path,
    *,
    env: Environment,
    repo_root: Path,
    fs: FileSystem | None = None,
) -> Tuple[List[Dict[str, str]], Optional[Path], str]:
    """Вернуть (instances, source_path, source_label).

    Приоритет:
      1) <env>.instances.{json,yaml,yml}
      2) instances.{json,yaml,yml}
      3) vars.instances / vars.index list в ближайшем <env>.json
    """

    for ext in ("json", "yaml", "yml"):
        p = connector_dir / f"{env.value}.instances.{ext}"
        if fs.exists(p) if fs else p.exists():
            return load_instances_from_file(p, fs=fs), p, f"instances:{p.name}"

    for ext in ("json", "yaml", "yml"):
        p = connector_dir / f"instances.{ext}"
        if fs.exists(p) if fs else p.exists():
            return load_instances_from_file(p, fs=fs), p, f"instances:{p.name}"

    env_file = find_nearest_env_file(connector_dir, env=env, repo_root=repo_root, fs=fs)
    if env_file is not None:
        vars_obj = load_vars_from_env_file(env_file, fs=fs)
        inst = load_instances_from_vars(vars_obj)
        if inst:
            return inst, env_file, f"vars:{env_file.name}"

    return [], None, ""
