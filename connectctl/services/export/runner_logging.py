from __future__ import annotations

from pathlib import Path
from typing import Any

from ...exporting import DetectedLayout
from .models import ExportFilters, ExportSelection


def log_all_scope(*, log, selection: ExportSelection, filters: ExportFilters) -> None:
    log.info("Export scope: --all (connectors=%s)", len(selection.names))
    if filters.filter_type:
        log.info("  filter: type=%s", filters.filter_type.value)
    if filters.filter_domain:
        log.info("  filter: domain=%s", filters.filter_domain)
    if filters.filter_system:
        log.info("  filter: system=%s", filters.filter_system)


def log_exported(
    *,
    log,
    remote_name: str,
    export_name: str,
    layout: DetectedLayout,
    written: Any,
) -> None:
    shown_name = (
        remote_name if remote_name == export_name else f"{remote_name} -> {export_name}"
    )
    if written:
        log.info(
            "exported: %s -> %s/%s/%s/%s (%s files)",
            shown_name,
            layout.domain,
            layout.connector_type.value,
            layout.system,
            layout.connector_dir,
            len(list(written)),
        )
    else:
        log.info("exported: %s (no files written)", shown_name)


def relpath(p: Any, *, repo_root: Path) -> str:
    if not p:
        return "(unknown)"
    try:
        return str(Path(p).relative_to(repo_root))
    except Exception:
        return str(p)
