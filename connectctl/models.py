from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from .lifecycle.models import ConnectorLifecycle


class Environment(str, Enum):
    dev = "dev"
    stage = "stage"
    prod = "prod"

    @classmethod
    def from_str(cls, value: str) -> "Environment":
        try:
            return cls(value)
        except ValueError as e:
            raise ValueError(
                f"Unknown environment: {value!r}. Expected one of: dev, stage, prod"
            ) from e


class ConnectorType(str, Enum):
    source = "source"
    sink = "sink"

    @classmethod
    def from_str(cls, value: str) -> "ConnectorType":
        try:
            return cls(value)
        except ValueError as e:
            raise ValueError(
                f"Unknown connector type: {value!r}. Expected one of: source, sink"
            ) from e


@dataclass(frozen=True)
class KafkaConfig:
    """Optional Kafka connection settings (used for metrics/reporting)."""

    bootstrap_servers: Sequence[str]
    # The rest are optional and only used if you enable secured clusters.
    security_protocol: Optional[str] = None
    sasl_mechanism: Optional[str] = None
    sasl_plain_username: Optional[str] = None
    sasl_plain_password: Optional[str] = None
    ssl_cafile: Optional[str] = None

    # AWS MSK IAM (SASL/OAUTHBEARER) support for Python metrics.
    # If you set sasl_mechanism=OAUTHBEARER, provide iam_region.
    iam_region: Optional[str] = None
    aws_profile: Optional[str] = None


@dataclass(frozen=True)
class SchemaRegistryConfig:
    """Optional Schema Registry connection settings.

    The config targets Confluent-compatible Schema Registry APIs, including
    Karapace-compatible deployments. It intentionally stores only transport
    details; governance behavior lives in services/commands.
    """

    urls: Sequence[str]
    username: Optional[str] = None
    password: Optional[str] = None
    timeout_seconds: float = 10.0


@dataclass(frozen=True)
class ClusterLifecycle:
    """Effective lifecycle state for a Kafka Connect cluster env scope."""

    disabled: bool = False
    reason: Optional[str] = None
    ticket: Optional[str] = None
    until: Optional[str] = None

    @property
    def enabled(self) -> bool:
        return not self.disabled

    @property
    def configured(self) -> bool:
        return bool(self.disabled or self.reason or self.ticket or self.until)

    @property
    def status(self) -> str:
        return "disabled" if self.disabled else "enabled"

    def merge(self, override: "ClusterLifecycle") -> "ClusterLifecycle":
        """Return lifecycle with monotonic disabled semantics.

        A narrower scope may refine metadata, but it cannot silently re-enable
        a broader disabled scope. Re-enable must be explicit: remove/change the
        disabling declaration that introduced the state.
        """

        return ClusterLifecycle(
            disabled=self.disabled or override.disabled,
            reason=override.reason or self.reason,
            ticket=override.ticket or self.ticket,
            until=override.until or self.until,
        )

    def to_meta(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "disabled": self.disabled,
            "status": self.status,
        }
        if self.reason:
            payload["reason"] = self.reason
        if self.ticket:
            payload["ticket"] = self.ticket
        if self.until:
            payload["until"] = self.until
        return payload


@dataclass(frozen=True)
class ConnectRuntimeConfig:
    """Kafka Connect runtime/control-plane metadata.

    `static_hosts` is the backward-compatible self-managed REST runtime.
    Operator-managed runtimes (Strimzi/CFK) can expose REST for diagnostics,
    but mutations must go through their CRD control plane by default.
    """

    type: str = "static_hosts"
    operator_managed: bool = False
    mutation_mode: str = "rest"
    rest_access: str = "direct"
    kubernetes_context: Optional[str] = None
    kubernetes_namespace: Optional[str] = None
    service: Optional[str] = None
    pod_selector: Optional[str] = None
    port: Optional[int] = None
    local_port: Optional[int] = None
    resource_name: Optional[str] = None
    connector_label_selector: Optional[str] = None
    provider: Optional[str] = None
    limitations: Tuple[str, ...] = ()

    @property
    def is_static_hosts(self) -> bool:
        return self.type == "static_hosts"

    @property
    def allows_rest_mutation(self) -> bool:
        return self.mutation_mode == "rest" and not self.operator_managed

    def to_payload(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "operator_managed": self.operator_managed,
            "mutation_mode": self.mutation_mode,
            "rest_access": self.rest_access,
            "kubernetes_context": self.kubernetes_context,
            "kubernetes_namespace": self.kubernetes_namespace,
            "service": self.service,
            "pod_selector": self.pod_selector,
            "resource_name": self.resource_name,
            "connector_label_selector": self.connector_label_selector,
            "provider": self.provider,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class ConnectClusterConfig:
    """Kafka Connect REST API endpoints for an environment."""

    env: Environment
    urls: Sequence[str]  # e.g. ["http://10.0.0.1:8083", ...]
    runtime: ConnectRuntimeConfig = field(default_factory=ConnectRuntimeConfig)
    kafka: Optional[KafkaConfig] = None
    schema_registry: Optional[SchemaRegistryConfig] = None
    # Render-time policy: config keys to remove from the final rendered connector config
    # for this cluster (e.g. when Connect side already defines them in connect.properties).
    render_prune_config_keys: Tuple[str, ...] = ()
    # Render-time variables injected into placeholder context for this target cluster.
    render_vars: Dict[str, Any] = field(default_factory=dict)
    # Optional cluster identifier (used for multi-cluster routing/reporting).
    # Backwards-compatible: if not provided, defaults to "default".
    name: str = "default"
    lifecycle: ClusterLifecycle = field(default_factory=ClusterLifecycle)


@dataclass(frozen=True)
class RepoConfig:
    root: Path
    connectors_root: Path
    ignore_dirs: Tuple[str, ...] = (
        ".git",
        ".idea",
        ".vscode",
        "__pycache__",
        "test",
        "tests",
        "ci",
        "connectctl",
        "__global",
        "__init_templates",
        "schemas",
    )


@dataclass(frozen=True)
class ConnectorPathInfo:
    """Metadata inferred from a connector manifest path."""

    path: Path  # absolute path
    relpath: Path  # relative to repo root
    domain: str
    connector_type: ConnectorType
    system: str  # postgres / mariadb / iceberg / ...
    connector_dir: str  # e.g. connector_acme__configuration
    env: Environment
    remainder: str  # portion after '<env>_' (without '.json')
    variant: Optional[str] = None  # sink subtype like 'events'/'flatten' (best-effort)
    mode: Optional[str] = None  # e.g. 'init' or 'cdc' (best-effort)


@dataclass(frozen=True)
class ConnectorManifest:
    """Final rendered manifest we send to Kafka Connect."""

    name: str
    config: Dict[str, Any]
    source_path: Path  # manifest file path that produced it
    info: ConnectorPathInfo
    lifecycle: ConnectorLifecycle = ConnectorLifecycle()

    def to_connect_upsert_payload(self) -> Dict[str, Any]:
        from .rendering.unset_config import assert_final_config_has_no_nulls

        assert_final_config_has_no_nulls(
            self.config,
            connector_name=self.name,
            command="connect-upsert",
        )
        # Kafka Connect PUT /connectors/{name}/config expects only the config map.
        return dict(self.config)


@dataclass(frozen=True)
class ConnectorStatus:
    name: str
    connector_state: str
    worker_id: Optional[str]
    task_states: Tuple[str, ...]  # states per task index
    raw: Dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.connector_state.upper() == "RUNNING" and all(
            s.upper() == "RUNNING" for s in self.task_states
        )


@dataclass(frozen=True)
class Plan:
    env: Environment
    to_apply: Tuple[Path, ...]  # connector manifest paths (env-specific) to apply
    to_delete_paths: Tuple[
        Path, ...
    ]  # deleted manifest paths (env-specific) to delete from Connect
