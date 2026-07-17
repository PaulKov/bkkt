from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Tuple

from ..ports import FileSystem


def _allocate_export_report_path(
    *,
    export_dir: Path,
    connector_name: str,
    fs: FileSystem | None = None,
) -> Tuple[Path, int]:
    """Выделить следующий путь под export-report (export__<name>__N.json)."""

    patt = re.compile(rf"^export__{re.escape(connector_name)}__(\d+)\.json$")
    max_n = 0

    if fs:
        if fs.is_dir(export_dir):
            for f in fs.iterdir(export_dir):
                if not fs.is_file(f):
                    continue
                m = patt.match(f.name)
                if not m:
                    continue
                try:
                    n = int(m.group(1))
                    max_n = max(max_n, n)
                except ValueError:
                    pass
    else:
        if export_dir.exists() and export_dir.is_dir():
            for f in export_dir.iterdir():
                if not f.is_file():
                    continue
                m = patt.match(f.name)
                if not m:
                    continue
                try:
                    n = int(m.group(1))
                    max_n = max(max_n, n)
                except ValueError:
                    pass

    export_number = max_n + 1
    return (
        export_dir / f"export__{connector_name}__{export_number}.json"
    ).resolve(), export_number


def build_export_report_payload(
    *,
    connector_name: str,
    env: str,
    export_number: int,
    save_diffs: bool,
    export_diffs: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Сформировать JSON-объект export-report."""

    return {
        "connector": connector_name,
        "env": env,
        "export_number": export_number,
        "export_params_type": (
            "overrides" if save_diffs else "exported_connector_config"
        ),
        "diffs": dict(export_diffs),
    }
