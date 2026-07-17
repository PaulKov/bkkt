from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

from ...exceptions import ConfigError
from ...models import Environment


@dataclass(frozen=True)
class RawClusterGroups:
    """Сырая секция clusters в виде group -> env -> raw_obj."""

    groups: Dict[str, Dict[Environment, Any]]
    legacy: bool


def _is_env_key(k: Any) -> bool:
    try:
        Environment.from_str(str(k).lower())
        return True
    except Exception:
        return False


def parse_raw_cluster_groups(clusters_raw: Any) -> RawClusterGroups:
    if not isinstance(clusters_raw, Mapping) or not clusters_raw:
        raise ConfigError("Config must contain non-empty 'clusters' mapping")

    # Legacy mode: clusters: {dev: {...}, stage: {...}, prod: {...}}
    if all(_is_env_key(k) for k in clusters_raw.keys()):
        env_map_raw: Dict[Environment, Any] = {}
        for env_str, env_cfg in clusters_raw.items():
            env = Environment.from_str(str(env_str).lower())
            env_map_raw[env] = env_cfg
        return RawClusterGroups(groups={"default": env_map_raw}, legacy=True)

    # Multi-cluster mode
    out: Dict[str, Dict[Environment, Any]] = {}
    for group_name, group_obj in clusters_raw.items():
        if not isinstance(group_obj, Mapping):
            raise ConfigError(f"clusters.{group_name} must be a mapping")
        env_map_raw = {}
        for env_str, env_cfg in group_obj.items():
            if str(env_str) == "lifecycle":
                continue
            env = Environment.from_str(str(env_str).lower())
            env_map_raw[env] = env_cfg
        if not env_map_raw:
            raise ConfigError(f"clusters.{group_name} must not be empty")
        out[str(group_name)] = env_map_raw

    return RawClusterGroups(groups=out, legacy=False)
