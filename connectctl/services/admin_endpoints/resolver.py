from __future__ import annotations

from typing import Any

from ...app.context import CliContext
from ...exceptions import ConfigError
from ...models import ConnectClusterConfig, Environment, SchemaRegistryConfig
from ...settings_clusters_kafka import parse_kafka_config
from ...settings_clusters_schema_registry import parse_schema_registry_config
from .models import (
    EffectiveKafkaEndpoint,
    EffectiveSchemaRegistryEndpoint,
    EndpointSource,
)
from .policy import AdminEndpointPolicy
from .repo_defaults import RawAdminScopeLoader, RepoAdminDefaultsLoader


class EffectiveAdminEndpointResolver:
    """Resolves Kafka/SR admin endpoints with consistent provenance."""

    def __init__(
        self,
        ctx: CliContext,
        *,
        defaults_loader: RepoAdminDefaultsLoader | None = None,
        raw_scope_loader: RawAdminScopeLoader | None = None,
        policy: AdminEndpointPolicy | None = None,
    ) -> None:
        self.ctx = ctx
        self.defaults_loader = defaults_loader or RepoAdminDefaultsLoader(ctx)
        self.raw_scope_loader = raw_scope_loader or RawAdminScopeLoader(ctx)
        self.policy = policy or AdminEndpointPolicy()

    def resolve_kafka(
        self,
        *,
        env: Environment,
        cluster: ConnectClusterConfig,
        override_bootstrap: str | None = None,
    ) -> EffectiveKafkaEndpoint:
        override = _split_csv(override_bootstrap)
        if override:
            raw_scope = self.raw_scope_loader.get(cluster.name, env)
            config = parse_kafka_config(
                {**dict(raw_scope.kafka or {}), "bootstrap_servers": list(override)}
            )
            if config is None:
                raise ConfigError("Kafka --bootstrap-server override is empty")
            return EffectiveKafkaEndpoint(
                config=config,
                source=EndpointSource.CLI_OVERRIDE,
                source_label=EndpointSource.CLI_OVERRIDE.value,
            )

        if cluster.kafka is not None:
            return EffectiveKafkaEndpoint(
                config=cluster.kafka,
                source=EndpointSource.CLUSTER_CONFIG,
                source_label=EndpointSource.CLUSTER_CONFIG.value,
            )

        raw_scope = self.raw_scope_loader.get(cluster.name, env)
        decision = self.policy.kafka_default_decision(
            cluster=cluster, raw_scope=raw_scope
        )
        defaults = self.defaults_loader.load(env)
        if decision.allowed and defaults.bootstrap_servers:
            config = parse_kafka_config(
                {
                    **dict(raw_scope.kafka or {}),
                    "bootstrap_servers": list(defaults.bootstrap_servers),
                }
            )
            if config is not None:
                return EffectiveKafkaEndpoint(
                    config=config,
                    source=EndpointSource.REPO_DEFAULTS,
                    source_label=defaults.source_label
                    or EndpointSource.REPO_DEFAULTS.value,
                )

        raise ConfigError(
            _kafka_missing_message(
                cluster=cluster,
                env=env,
                reason=decision.reason,
                has_defaults=bool(defaults.bootstrap_servers),
            )
        )

    def resolve_schema_registry(
        self,
        *,
        env: Environment,
        cluster: ConnectClusterConfig,
        override_url: str | None = None,
        timeout_seconds: Any = None,
    ) -> EffectiveSchemaRegistryEndpoint:
        override = str(override_url or "").strip()
        if override:
            return EffectiveSchemaRegistryEndpoint(
                config=_schema_config_from_url(
                    override, timeout_seconds=timeout_seconds
                ),
                source=EndpointSource.CLI_OVERRIDE,
                source_label=EndpointSource.CLI_OVERRIDE.value,
            )

        if cluster.schema_registry is not None:
            return EffectiveSchemaRegistryEndpoint(
                config=cluster.schema_registry,
                source=EndpointSource.CLUSTER_CONFIG,
                source_label=EndpointSource.CLUSTER_CONFIG.value,
            )

        raw_scope = self.raw_scope_loader.get(cluster.name, env)
        decision = self.policy.schema_registry_default_decision(
            cluster=cluster, raw_scope=raw_scope
        )
        defaults = self.defaults_loader.load(env)
        if decision.allowed and defaults.schema_registry_urls:
            config = parse_schema_registry_config(
                {
                    **dict(raw_scope.schema_registry or {}),
                    "urls": list(defaults.schema_registry_urls),
                }
            )
            if config is not None:
                return EffectiveSchemaRegistryEndpoint(
                    config=config,
                    source=EndpointSource.REPO_DEFAULTS,
                    source_label=defaults.source_label
                    or EndpointSource.REPO_DEFAULTS.value,
                )

        raise ConfigError(
            _schema_missing_message(
                cluster=cluster,
                env=env,
                reason=decision.reason,
                has_defaults=bool(defaults.schema_registry_urls),
            )
        )


def _schema_config_from_url(url: str, *, timeout_seconds: Any) -> SchemaRegistryConfig:
    timeout = _float_timeout(timeout_seconds)
    urls = tuple(part.strip().rstrip("/") for part in url.split(",") if part.strip())
    return SchemaRegistryConfig(urls=urls, timeout_seconds=timeout)


def _float_timeout(value: Any) -> float:
    try:
        return float(value) if value is not None else 10.0
    except (TypeError, ValueError):
        return 10.0


def _split_csv(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, (list, tuple)):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return ()


def _kafka_missing_message(
    *,
    cluster: ConnectClusterConfig,
    env: Environment,
    reason: str | None,
    has_defaults: bool,
) -> str:
    hint = (
        "add clusters.<group>.<env>.kafka.bootstrap_servers to connectctl.yaml, "
        "set __global/<env>.json vars.kafka.bootstrap_servers for eligible scopes, "
        "or pass --bootstrap-server"
    )
    defaults = "repo defaults exist" if has_defaults else "repo defaults are missing"
    return (
        f"clusters.{cluster.name}.{env.value}.kafka is not configured for Kafka "
        f"admin commands ({reason or defaults}); {hint}"
    )


def _schema_missing_message(
    *,
    cluster: ConnectClusterConfig,
    env: Environment,
    reason: str | None,
    has_defaults: bool,
) -> str:
    hint = (
        "add clusters.<group>.<env>.schema_registry.urls to connectctl.yaml, "
        "set __global/<env>.json vars.kafka.schema_registry_url for eligible scopes, "
        "or pass --url"
    )
    defaults = "repo defaults exist" if has_defaults else "repo defaults are missing"
    return (
        f"clusters.{cluster.name}.{env.value}.schema_registry is not configured "
        f"({reason or defaults}); {hint}"
    )
