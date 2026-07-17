"""Парсинг секции `clusters` из connectctl.yaml.

Этот модуль — *публичный фасад* для разборки кластеров. Реальная логика
разнесена по маленьким модулям:

- :mod:`connectctl.settings_clusters_kafka` — разбор секции kafka (опционально)
- :mod:`connectctl.settings_clusters_env` — разбор env-конфига кластера
- :mod:`connectctl.settings_clusters_inheritance` — from_cluster_group_env(...)

Важно: файл оставлен ради обратной совместимости импортов.
"""

from __future__ import annotations
from typing import Any, Dict, Mapping

from .exceptions import ConfigError
from .models import ClusterLifecycle, ConnectClusterConfig, Environment
from .settings_clusters_env import parse_cluster_env_cfg
from .settings_clusters_inheritance import ClusterGroupEnvResolver
from .settings_clusters_lifecycle import (
    apply_effective_lifecycle,
    parse_cluster_lifecycle,
    parse_root_lifecycle_overrides,
)


def _is_env_key(k: Any) -> bool:
    try:
        Environment.from_str(str(k).lower())
        return True
    except Exception:
        return False


def parse_cluster_groups(
    clusters_raw: Mapping[str, Any],
    *,
    root_lifecycle_raw: Any = None,
) -> Dict[str, Dict[Environment, ConnectClusterConfig]]:
    """Разобрать секцию `clusters` из connectctl.yaml.

    Поддерживаются два формата:

    1) Legacy:
       clusters:
         dev: {...}
         stage: {...}
         prod: {...}

       → group_name = "default"

    2) Multi-cluster:
       clusters:
         acme-main:
           dev: {...}
           stage: {...}
         acme-external:
           prod: {...}

    Дополнительно поддерживается функция-наследование:

      from_cluster_group_env(<group>, <selector>)

    Примеры:
      dev: from_cluster_group_env(acme-main, 'all')
      prod:
        kafka: from_cluster_group_env(acme-main, 'kafka')
        connect:
          port: from_cluster_group_env(acme-main, 'connect.port')
          hosts: ['10.0.0.1']

    selector:
      - all → вернуть целиком env-конфиг группы
      - kafka / connect.port → вернуть значение по dot-path
      - connect.hosts,connect.port → вернуть mapping с выбранными параметрами

    Важно: на уровне env (clusters.<group>.<env>) результат должен быть mapping,
    иначе будет ошибка.
    """

    if not isinstance(clusters_raw, Mapping) or not clusters_raw:
        raise ConfigError("Config must contain non-empty 'clusters' mapping")

    root_overrides = parse_root_lifecycle_overrides(root_lifecycle_raw)

    # Backwards-compatible mode: clusters: {dev: {...}, stage: {...}, prod: {...}}
    if all(_is_env_key(k) for k in clusters_raw.keys()):
        group_name = "default"
        env_map: Dict[Environment, ConnectClusterConfig] = {}
        for env_str, env_cfg in clusters_raw.items():
            env = Environment.from_str(str(env_str).lower())
            if not isinstance(env_cfg, Mapping):
                raise ConfigError(f"clusters.{env.value} must be a mapping")
            env_cfg = apply_effective_lifecycle(
                env_cfg,
                group_lifecycle=ClusterLifecycle(),
                root_overrides=root_overrides,
                cluster=group_name,
                env=env.value,
            )
            env_map[env] = parse_cluster_env_cfg(
                cluster_name=group_name, env=env, env_cfg=env_cfg
            )
        return {group_name: env_map}

    # New multi-cluster mode (with optional from_cluster_group_env inheritance)
    raw_groups: Dict[str, Dict[Environment, Any]] = {}
    group_lifecycles: Dict[str, ClusterLifecycle] = {}
    for cluster_name, group_obj in clusters_raw.items():
        if not isinstance(group_obj, Mapping):
            raise ConfigError(f"clusters.{cluster_name} must be a mapping")

        group_lifecycles[str(cluster_name)] = parse_cluster_lifecycle(
            group_obj.get("lifecycle"),
            path=f"clusters.{cluster_name}.lifecycle",
        )
        env_map_raw: Dict[Environment, Any] = {}
        for env_str, env_cfg in group_obj.items():
            if str(env_str) == "lifecycle":
                continue
            env = Environment.from_str(str(env_str).lower())
            env_map_raw[env] = env_cfg
        if not env_map_raw:
            raise ConfigError(f"clusters.{cluster_name} must not be empty")
        raw_groups[str(cluster_name)] = env_map_raw

    resolver = ClusterGroupEnvResolver(
        raw_groups,
        group_lifecycles=group_lifecycles,
        root_overrides=root_overrides,
    )

    cluster_groups: Dict[str, Dict[Environment, ConnectClusterConfig]] = {}
    for group_name, env_raw in raw_groups.items():
        env_cfg_map: Dict[Environment, ConnectClusterConfig] = {}
        for env in env_raw.keys():
            env_cfg = resolver.resolve_env_mapping(group_name, env=env)
            env_cfg_map[env] = parse_cluster_env_cfg(
                cluster_name=group_name, env=env, env_cfg=env_cfg
            )
        cluster_groups[group_name] = env_cfg_map

    return cluster_groups


__all__ = [
    "parse_cluster_groups",
    "parse_cluster_env_cfg",
]
