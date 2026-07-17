from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..exceptions import ConfigError


def _find_planned_env_manifest(
    planned_files: Mapping[Path, Any], connector_name: str
) -> Path:
    """Найти env-манифест (planned file) для коннектора по его имени.

    build_generic_planned_files(...) создаёт planned env manifest с полем {"name": <connector_name>}.
    """

    for pth, obj in planned_files.items():
        if isinstance(obj, dict) and obj.get("name") == connector_name:
            return Path(pth)
    raise ConfigError(f"could not determine env manifest path for {connector_name}")
