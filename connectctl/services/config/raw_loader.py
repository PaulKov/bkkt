from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml

from ...exceptions import ConfigError
from ...ports.filesystem import FileSystem
from ...utils import expand_env_in_obj


@dataclass(frozen=True)
class RawConfig:
    """Сырые данные connectctl.yaml после safe_load + expand env vars."""

    data: Dict[str, Any]
    path: Path


def load_raw_config(path: Path, *, fs: FileSystem) -> RawConfig:
    if not fs.exists(path):
        raise ConfigError(f"Config file not found: {path}")

    raw_text = fs.read_text(path, encoding="utf-8").strip()
    if not raw_text:
        raise ConfigError(f"Config file is empty: {path}")

    suffix = path.suffix.lower()
    if suffix in {".yml", ".yaml"}:
        data = yaml.safe_load(raw_text) or {}
    elif suffix == ".json":
        data = json.loads(raw_text)
    else:
        raise ConfigError(
            f"Unsupported config format: {path.suffix}. Use YAML or JSON."
        )

    if not isinstance(data, Mapping):
        raise ConfigError("Config root must be a mapping (YAML object)")

    data2 = expand_env_in_obj(dict(data))
    return RawConfig(data=dict(data2), path=path)
