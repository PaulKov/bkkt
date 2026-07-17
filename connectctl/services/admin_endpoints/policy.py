from __future__ import annotations

from fnmatch import fnmatch
from typing import Sequence

from ...models import ConnectClusterConfig
from .models import EndpointDecision, EndpointSource, RawAdminScope


KAFKA_BOOTSTRAP_KEYS: tuple[str, ...] = (
    "bootstrap.servers",
    "consumer.override.bootstrap.servers",
    "producer.override.bootstrap.servers",
    "admin.override.bootstrap.servers",
    "iceberg.kafka.bootstrap.servers",
)

SCHEMA_REGISTRY_KEYS: tuple[str, ...] = (
    "schema.registry.url",
    "key.converter.schema.registry.url",
    "value.converter.schema.registry.url",
)


class AdminEndpointPolicy:
    """Decides when repo render defaults may power admin diagnostics."""

    def kafka_default_decision(
        self, *, cluster: ConnectClusterConfig, raw_scope: RawAdminScope
    ) -> EndpointDecision:
        if _matches_any(cluster.render_prune_config_keys, KAFKA_BOOTSTRAP_KEYS):
            return EndpointDecision(
                allowed=False,
                source=EndpointSource.WORKER_MANAGED,
                reason=(
                    "Kafka bootstrap is worker-managed/pruned by "
                    "`render.prune_config_keys` "
                    f"({', '.join(KAFKA_BOOTSTRAP_KEYS)}); "
                    "do not inherit repo defaults."
                ),
            )
        if raw_scope.has_kafka:
            return EndpointDecision(allowed=True, source=EndpointSource.REPO_DEFAULTS)
        return EndpointDecision(
            allowed=False,
            source=EndpointSource.MISSING,
            reason="cluster scope has no `kafka:` block",
        )

    def schema_registry_default_decision(
        self, *, cluster: ConnectClusterConfig, raw_scope: RawAdminScope
    ) -> EndpointDecision:
        if _matches_any(cluster.render_prune_config_keys, SCHEMA_REGISTRY_KEYS):
            return EndpointDecision(
                allowed=False,
                source=EndpointSource.WORKER_MANAGED,
                reason=(
                    "Schema Registry config is pruned by "
                    "`render.prune_config_keys` "
                    f"({', '.join(SCHEMA_REGISTRY_KEYS)}); "
                    "do not inherit repo defaults."
                ),
            )
        if raw_scope.has_schema_registry or raw_scope.has_kafka:
            return EndpointDecision(allowed=True, source=EndpointSource.REPO_DEFAULTS)
        return EndpointDecision(
            allowed=False,
            source=EndpointSource.MISSING,
            reason="cluster scope has no `schema_registry:` or `kafka:` block",
        )


def _matches_any(patterns: Sequence[str], candidates: Sequence[str]) -> bool:
    return any(
        fnmatch(candidate, pattern) for pattern in patterns for candidate in candidates
    )
