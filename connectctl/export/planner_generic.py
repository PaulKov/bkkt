from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

from ..models import ConnectorType
from ..repo import ConnectorRepo

from .layout import (
    DetectedLayout,
    build_sink_manifest_filename,
    build_source_manifest_filename,
)


def build_generic_planned_files(
    *,
    repo: ConnectorRepo,
    layout: DetectedLayout,
    connector_name: str,
    remote_config: Mapping[str, Any],
) -> Dict[Path, Dict[str, Any]]:
    """Построить минимальный план экспорта.

    План всегда включает env-манифест (только `name`), который затем может быть
    дополнен (например, `config`) в зависимости от флагов экспорта.

    Путь определяется на основе `layout`.
    """

    connectors_root = repo.cfg.connectors_root
    target_dir = (
        connectors_root
        / layout.domain
        / layout.connector_type.value
        / layout.system
        / layout.connector_dir
    )

    if layout.connector_type == ConnectorType.sink:
        env_file = target_dir / build_sink_manifest_filename(layout, connector_name)
    else:
        env_file = target_dir / build_source_manifest_filename(connector_name)

    planned: Dict[Path, Dict[str, Any]] = {}
    planned[env_file.resolve()] = {
        "name": connector_name,
    }
    return planned
