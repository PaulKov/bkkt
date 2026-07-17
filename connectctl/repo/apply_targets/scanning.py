from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from ...models import Environment
from ...ports import FileSystem
from ..scanner import ConnectorRepo


def scan_dir_for_env(
    repo: ConnectorRepo,
    directory: Path,
    env: Environment,
    *,
    fs: FileSystem | None = None,
) -> Tuple[List[Path], List[Path]]:
    """Вернуть (normal_files, template_files)"""

    normal: List[Path] = []
    templates: List[Path] = []
    files = fs.glob(directory, "**/*.json") if fs else directory.rglob("*.json")
    for f in sorted(files, key=lambda p: str(p)):
        if not repo.is_deployable_connector_file(f):
            continue
        info = repo.parse_connector_path(f, must_exist=False)
        if info.env != env:
            continue
        if "${" in f.name:
            templates.append(f)
        else:
            normal.append(f)

    return normal, templates
