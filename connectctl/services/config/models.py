from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from ...models import ClusterLifecycle, Environment


@dataclass(frozen=True)
class ConfigWarning:
    code: str
    message: str


@dataclass(frozen=True)
class ConfigValidationResult:
    config_path: Path
    default_cluster: str
    cluster_groups: Dict[str, Sequence[Environment]]
    warnings: Tuple[ConfigWarning, ...] = ()
    ok: bool = True


@dataclass(frozen=True)
class InheritanceCall:
    path: str
    raw: str
    ref_group: str
    selector: str


@dataclass(frozen=True)
class ConfigExplainResult:
    config_path: Path
    cluster_group: str
    env: Environment
    resolved_env_cfg: Dict[str, Any]
    connect_urls: Tuple[str, ...]
    kafka: Optional[Dict[str, Any]] = None
    inheritance_calls: Tuple[InheritanceCall, ...] = ()


@dataclass(frozen=True)
class ConfigClusterEnvInventory:
    env: Environment
    connect_urls: Tuple[str, ...]
    connect_hosts: Tuple[str, ...]
    lifecycle: ClusterLifecycle = ClusterLifecycle()
    runtime_type: str = "static_hosts"
    runtime_operator_managed: bool = False
    runtime_mutation_mode: str = "rest"
    runtime_rest_access: str = "direct"
    runtime_kubernetes_context: Optional[str] = None
    runtime_kubernetes_namespace: Optional[str] = None
    runtime_service: Optional[str] = None
    runtime_pod_selector: Optional[str] = None
    runtime_resource_name: Optional[str] = None
    runtime_connector_label_selector: Optional[str] = None
    runtime_provider: Optional[str] = None
    runtime_limitations: Tuple[str, ...] = ()
    kafka_bootstrap_servers: Tuple[str, ...] = ()
    kafka_hosts: Tuple[str, ...] = ()
    kafka_security_protocol: Optional[str] = None
    kafka_sasl_mechanism: Optional[str] = None
    kafka_iam_region: Optional[str] = None
    kafka_aws_profile: Optional[str] = None
    kafka_bootstrap_source: Optional[str] = None
    schema_registry_urls: Tuple[str, ...] = ()
    schema_registry_source: Optional[str] = None
    render_prune_config_keys: Tuple[str, ...] = ()
    render_vars: Dict[str, Any] | None = None
    notes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ConfigClusterInventory:
    name: str
    is_default: bool
    envs: Tuple[ConfigClusterEnvInventory, ...]


@dataclass(frozen=True)
class ConfigClustersResult:
    config_path: Path
    default_cluster: str
    clusters: Tuple[ConfigClusterInventory, ...]
