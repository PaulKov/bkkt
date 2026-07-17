from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class EndpointSource(str, Enum):
    CLI_OVERRIDE = "cli override"
    CLUSTER_CONFIG = "cluster config"
    REPO_DEFAULTS = "repo defaults"
    WORKER_MANAGED = "worker-managed"
    MISSING = "missing"


@dataclass(frozen=True)
class RepoAdminDefaults:
    bootstrap_servers: tuple[str, ...] = ()
    schema_registry_urls: tuple[str, ...] = ()
    source_label: str | None = None


@dataclass(frozen=True)
class RawAdminScope:
    kafka: Mapping[str, Any] | None = None
    schema_registry: Mapping[str, Any] | None = None

    @property
    def has_kafka(self) -> bool:
        return self.kafka is not None

    @property
    def has_schema_registry(self) -> bool:
        return self.schema_registry is not None


@dataclass(frozen=True)
class EndpointDecision:
    allowed: bool
    source: EndpointSource
    reason: str | None = None


@dataclass(frozen=True)
class EffectiveKafkaEndpoint:
    config: Any
    source: EndpointSource
    source_label: str


@dataclass(frozen=True)
class EffectiveSchemaRegistryEndpoint:
    config: Any
    source: EndpointSource
    source_label: str
