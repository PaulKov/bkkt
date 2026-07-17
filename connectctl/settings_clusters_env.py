from __future__ import annotations

from typing import Any, Mapping

from .exceptions import ConfigError
from .models import ConnectClusterConfig, Environment
from .settings_clusters_kafka import parse_kafka_config
from .settings_clusters_lifecycle import parse_cluster_lifecycle
from .settings_clusters_runtime import parse_connect_runtime
from .settings_clusters_schema_registry import parse_schema_registry_config


def parse_cluster_env_cfg(
    *, cluster_name: str, env: Environment, env_cfg: Mapping[str, Any]
) -> ConnectClusterConfig:
    """Разобрать env-часть конфигурации кластера.

    Ожидаемый формат:

    clusters.<group>.<env>:
      connect:
        hosts: ["host1", "host2"]
        port: 8083
        scheme: http
      kafka: ...  # опционально (для Kafka inventory)
      schema_registry: ...  # опционально (для Schema Registry governance)
    """
    connect_cfg = env_cfg.get("connect", {}) or {}
    hosts = connect_cfg.get("hosts") or []
    if isinstance(hosts, str):
        hosts = [h.strip() for h in hosts.split(",") if h.strip()]

    port = int(connect_cfg.get("port", 8083))
    scheme = str(connect_cfg.get("scheme", "http"))

    legacy_urls = [f"{scheme}://{h}:{port}" for h in hosts]
    runtime, urls = parse_connect_runtime(
        connect_cfg,
        cluster_name=cluster_name,
        env_name=env.value,
        legacy_urls=legacy_urls,
    )
    if runtime.is_static_hosts and not urls:
        raise ConfigError(
            f"clusters.{cluster_name}.{env.value}.connect.hosts must not be empty"
        )

    kafka_cfg = parse_kafka_config(env_cfg.get("kafka"))
    schema_registry_cfg = parse_schema_registry_config(env_cfg.get("schema_registry"))

    render_cfg = env_cfg.get("render") or {}
    if not isinstance(render_cfg, Mapping):
        render_cfg = {}
    prune_cfg = render_cfg.get("prune_config_keys") or []
    if isinstance(prune_cfg, str):
        # Allow comma-separated string in YAML, e.g. "a.*,b.*"
        prune_cfg = [p.strip() for p in prune_cfg.split(",") if p.strip()]
    prune_keys = tuple(str(p).strip() for p in prune_cfg if str(p).strip())
    vars_cfg = render_cfg.get("vars") or {}
    if not isinstance(vars_cfg, Mapping):
        vars_cfg = {}
    render_vars = {str(k): v for k, v in vars_cfg.items()}
    return ConnectClusterConfig(
        env=env,
        urls=urls,
        runtime=runtime,
        kafka=kafka_cfg,
        schema_registry=schema_registry_cfg,
        render_prune_config_keys=prune_keys,
        render_vars=render_vars,
        name=cluster_name,
        lifecycle=parse_cluster_lifecycle(
            env_cfg.get("lifecycle"),
            path=f"clusters.{cluster_name}.{env.value}.lifecycle",
        ),
    )
