from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List

from ...ports import FileSystem


def relpath(repo_root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(repo_root))
    except Exception:
        return str(p)


def ensure_dir(
    path: Path,
    *,
    fs: FileSystem,
    repo_root: Path,
    dry_run: bool,
    log: logging.Logger,
) -> None:
    if dry_run:
        log.info("[dry-run] would create directory: %s", relpath(repo_root, path))
        return
    fs.mkdirs(path, exist_ok=True)


def write_json(
    path: Path,
    obj: dict,
    *,
    fs: FileSystem,
    repo_root: Path,
    dry_run: bool,
    created: List[Path],
    log: logging.Logger,
) -> None:
    if dry_run:
        log.info("[dry-run] would write: %s", relpath(repo_root, path))
        created.append(path)
        return

    raw = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fs.write_text(path, raw, encoding="utf-8")
    created.append(path)


def maybe_write_all_json(
    all_path: Path,
    *,
    fs: FileSystem,
    repo_root: Path,
    dry_run: bool,
    force: bool,
    created: List[Path],
    dataset: str,
    connector_type: str,
    layer: str,
    log: logging.Logger,
) -> None:
    if fs.exists(all_path) and not force:
        log.info("skip (exists): %s", relpath(repo_root, all_path))
        return

    vars_obj: Dict[str, str] = {}
    if dataset:
        vars_obj["dataset"] = dataset
    if connector_type == "sink" and layer:
        vars_obj["layer"] = layer

    obj = {"vars": vars_obj, "config": {}}
    write_json(
        all_path,
        obj,
        fs=fs,
        repo_root=repo_root,
        dry_run=dry_run,
        created=created,
        log=log,
    )
