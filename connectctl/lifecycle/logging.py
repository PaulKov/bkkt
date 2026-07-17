from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .models import ConnectorLifecycle


def format_lifecycle_banner_lines(
    *,
    lifecycle: ConnectorLifecycle,
    action: str,
    connector_name: str,
    manifest_path: Path,
    repo_root: Optional[Path] = None,
) -> List[str]:
    if not lifecycle.disabled:
        return []

    path_label = _relpath(manifest_path, repo_root)
    lines = [
        f"===== {action}: connector lifecycle is DISABLED =====",
        f"connector: {connector_name}",
        f"manifest: {path_label}",
        f"reason: {lifecycle.reason or '(missing)'}",
    ]
    if lifecycle.ticket:
        lines.append(f"ticket: {lifecycle.ticket}")
    if lifecycle.until:
        lines.append(f"until: {lifecycle.until}")
    if lifecycle.disabled_sources:
        lines.append("disabled by:")
        lines.extend(f" - {src}" for src in lifecycle.disabled_sources)
    lines.append("=" * 46)
    return lines


def log_lifecycle_banner(
    *,
    logger,
    lifecycle: ConnectorLifecycle,
    action: str,
    connector_name: str,
    manifest_path: Path,
    repo_root: Optional[Path] = None,
) -> None:
    for line in format_lifecycle_banner_lines(
        lifecycle=lifecycle,
        action=action,
        connector_name=connector_name,
        manifest_path=manifest_path,
        repo_root=repo_root,
    ):
        logger.warning("%s", line)


def _relpath(path: Path, repo_root: Optional[Path]) -> str:
    if repo_root is None:
        return str(path)
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return str(path)
