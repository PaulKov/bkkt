from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..exceptions import ConfigError
from ..models import ConnectorType
from ..rendering.json_loader import load_json_file
from ..repo import ConnectorRepo
from .layout_files import build_sink_manifest_filename
from .layout_models import DetectedLayout


def resolve_sink_export_collision(
    *,
    repo: ConnectorRepo,
    layout: DetectedLayout,
    connector_name: str,
    force: bool,
    enabled: bool,
) -> Tuple[DetectedLayout, Optional[Dict[str, Any]]]:
    """Detect sink export path collisions and (optionally) auto-suffix connector_dir with __<index>.

    Collision means: the computed env manifest file already exists in the repo for a different connector name.

    Returns: (possibly_updated_layout, info)
      info is None when no collision handling was applied.
    """
    fs = repo.fs

    def _exists(p: Path) -> bool:
        return fs.exists(p) if fs else p.exists()

    if layout.connector_type != ConnectorType.sink or force:
        return layout, None

    connectors_root = repo.cfg.connectors_root
    base_dir = (
        connectors_root
        / layout.domain
        / layout.connector_type.value
        / layout.system
        / layout.connector_dir
    )
    env_file = (
        base_dir / build_sink_manifest_filename(layout, connector_name)
    ).resolve()
    if not _exists(env_file):
        return layout, None

    existing_name: Optional[str] = None
    try:
        existing_obj = load_json_file(env_file, fs=fs)
        if isinstance(existing_obj, dict):
            existing_name = existing_obj.get("name")
    except Exception:
        existing_name = None

    # Same connector re-export: treat as no collision.
    if existing_name == connector_name:
        return layout, None

    # Collision found.
    info: Dict[str, Any] = {
        "collision": True,
        "existing_name": existing_name,
        "env_file": env_file,
        "original_connector_dir": layout.connector_dir,
    }
    if not enabled:
        return layout, info

    m = re.search(r"\.(\d+)$", connector_name)
    if not m:
        raise ConfigError(
            f"Export collision: {env_file} already exists for a different connector ({existing_name or 'unknown'}). "
            "Cannot auto-suffix because connector name has no trailing .<index>. "
            "Use --connector-dir to choose a unique directory, or disable auto-suffixing."
        )
    idx = m.group(1)

    base = layout.connector_dir
    # Keep existing suffix if already present.
    candidate = base if base.endswith(f"__{idx}") else f"{base}__{idx}"
    attempt = 0
    while True:
        cand_layout = DetectedLayout(**{**layout.__dict__, "connector_dir": candidate})
        cand_dir = (
            connectors_root
            / cand_layout.domain
            / cand_layout.connector_type.value
            / cand_layout.system
            / cand_layout.connector_dir
        )
        cand_env_file = (
            cand_dir / build_sink_manifest_filename(cand_layout, connector_name)
        ).resolve()
        if not _exists(cand_env_file):
            info.update(
                {
                    "chosen_connector_dir": candidate,
                    "index": idx,
                    "chosen_env_file": cand_env_file,
                }
            )
            return cand_layout, info

        # If candidate already contains the same connector, we can treat as no collision.
        try:
            cand_obj = load_json_file(cand_env_file, fs=fs)
            cand_name = cand_obj.get("name") if isinstance(cand_obj, dict) else None
        except Exception:
            cand_name = None
        if cand_name == connector_name:
            return cand_layout, None

        attempt += 1
        if attempt > 50:
            raise ConfigError(
                f"Export collision: too many existing variants for {base} with index={idx}. "
                "Use --connector-dir to choose a unique directory explicitly."
            )
        candidate = f"{base}__{idx}_{attempt}"
