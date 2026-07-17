from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..exceptions import LifecycleDisabledError
from ..models import ConnectorManifest
from .logging import log_lifecycle_banner


def raise_if_manifest_disabled(
    *,
    manifest: ConnectorManifest,
    logger,
    repo_root: Optional[Path] = None,
    action: str = "BLOCK",
    command: str = "deploy",
) -> None:
    if not manifest.lifecycle.disabled:
        return
    log_lifecycle_banner(
        logger=logger,
        lifecycle=manifest.lifecycle,
        action=action,
        connector_name=manifest.name,
        manifest_path=manifest.source_path,
        repo_root=repo_root,
    )
    raise LifecycleDisabledError(
        f"Connector {manifest.name} is disabled via connectctl.lifecycle; refusing to {command}. "
        f"Reason: {manifest.lifecycle.reason}"
    )


def log_disabled_manifest_skip(
    *,
    manifest: ConnectorManifest,
    logger,
    repo_root: Optional[Path] = None,
    action: str = "SKIP",
) -> None:
    if not manifest.lifecycle.disabled:
        return
    log_lifecycle_banner(
        logger=logger,
        lifecycle=manifest.lifecycle,
        action=action,
        connector_name=manifest.name,
        manifest_path=manifest.source_path,
        repo_root=repo_root,
    )
