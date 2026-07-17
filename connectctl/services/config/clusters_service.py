from __future__ import annotations

import argparse
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import urlparse

from ...app.context import CliContext
from ...cli_helpers.default_scope_ux import (
    EffectiveValue,
    effective_value,
    log_effective_values,
)
from ...cli_helpers.explicit_args import was_explicit
from ...exceptions import ConfigError
from ...logging_utils import get_logger
from ...models import ConnectClusterConfig, Environment
from ...output import (
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
)
from ...services.admin_endpoints.resolver import EffectiveAdminEndpointResolver
from ...utils.masking import mask_secrets_in_obj
from .models import (
    ConfigClusterEnvInventory,
    ConfigClusterInventory,
    ConfigClustersResult,
)
from .clusters_text import ClusterDisplayOptions, build_clusters_text
from .selection import (
    parse_cluster_group_filter,
    parse_env_filter,
    render_cluster_group_filter,
    render_env_filter,
    select_cluster_groups,
    select_envs,
)


class ConfigClustersService:
    """Build a self-service inventory of cluster groups from `connectctl.yaml`."""

    def __init__(self, *, ctx: CliContext, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)

    def run(self, args: argparse.Namespace) -> int:
        fmt = resolve_output_format(args)
        group_filter = parse_cluster_group_filter(getattr(args, "cluster_group", None))
        env_filter = parse_env_filter(getattr(args, "env", None))
        show_render_vars = bool(getattr(args, "show_render_vars", False))
        display = ClusterDisplayOptions.from_args(args)

        log_effective_values(
            self.log,
            command="config clusters",
            values=(
                _cluster_group_effective_value(
                    args,
                    render_cluster_group_filter(group_filter),
                ),
                effective_value(args, "env", render_env_filter(env_filter)),
                effective_value(args, "output", fmt.value),
                effective_value(args, "show_render_vars", show_render_vars),
                effective_value(args, "view", display.view),
            ),
        )

        result = self.build_inventory(
            group_filter=group_filter,
            env_filter=env_filter,
            show_render_vars=show_render_vars,
        )
        payload = _result_to_payload(result)

        if is_machine_output(fmt):
            write_payload(payload, fmt=fmt)
        else:
            write_text(
                build_clusters_text(
                    result,
                    show_render_vars=show_render_vars,
                    display=display,
                )
            )
        return 0

    def build_inventory(
        self,
        *,
        group_filter: Optional[set[str]],
        env_filter: Optional[set[Environment]],
        show_render_vars: bool,
    ) -> ConfigClustersResult:
        groups = select_cluster_groups(
            self.ctx.settings.cluster_groups.keys(), include=group_filter
        )
        endpoint_resolver = EffectiveAdminEndpointResolver(self.ctx)

        inventories: List[ConfigClusterInventory] = []
        for group in groups:
            env_map = self.ctx.settings.cluster_groups[group]
            envs = select_envs(env_map.keys(), include=env_filter)
            inventories.append(
                ConfigClusterInventory(
                    name=group,
                    is_default=group == self.ctx.settings.default_cluster,
                    envs=tuple(
                        _env_inventory(
                            env_map[env],
                            show_render_vars=show_render_vars,
                            endpoint_resolver=endpoint_resolver,
                        )
                        for env in envs
                    ),
                )
            )

        return ConfigClustersResult(
            config_path=self.ctx.config_path,
            default_cluster=self.ctx.settings.default_cluster,
            clusters=tuple(inventories),
        )


def _env_inventory(
    cluster: ConnectClusterConfig,
    *,
    show_render_vars: bool,
    endpoint_resolver: EffectiveAdminEndpointResolver,
) -> ConfigClusterEnvInventory:
    prune_keys = tuple(cluster.render_prune_config_keys)
    notes: list[str] = []
    kafka = None
    kafka_bootstrap_servers: tuple[str, ...] = ()
    kafka_bootstrap_source: str | None = None
    try:
        kafka_endpoint = endpoint_resolver.resolve_kafka(
            env=cluster.env, cluster=cluster
        )
        kafka = kafka_endpoint.config
        kafka_bootstrap_servers = tuple(kafka_endpoint.config.bootstrap_servers)
        kafka_bootstrap_source = kafka_endpoint.source_label
    except ConfigError as exc:
        kafka_bootstrap_source = _blocked_source(str(exc), blocked="worker-managed")
        notes.append(
            _inventory_note(
                str(exc),
                default="Kafka bootstrap is not configured for this cluster scope",
            )
        )

    schema_registry_urls: tuple[str, ...] = ()
    schema_registry_source: str | None = None
    try:
        schema_endpoint = endpoint_resolver.resolve_schema_registry(
            env=cluster.env, cluster=cluster
        )
        schema_registry_urls = tuple(schema_endpoint.config.urls)
        schema_registry_source = schema_endpoint.source_label
    except ConfigError as exc:
        schema_registry_source = _blocked_source(str(exc), blocked="pruned")
        notes.append(
            _inventory_note(
                str(exc),
                default="Schema Registry is not configured for this cluster scope",
            )
        )

    render_vars: Dict[str, Any] | None = None
    if show_render_vars:
        masked = mask_secrets_in_obj(dict(cluster.render_vars))
        render_vars = dict(masked) if isinstance(masked, Mapping) else {}

    return ConfigClusterEnvInventory(
        env=cluster.env,
        connect_urls=tuple(str(url) for url in cluster.urls),
        connect_hosts=tuple(_connect_host(url) for url in cluster.urls),
        lifecycle=cluster.lifecycle,
        runtime_type=cluster.runtime.type,
        runtime_operator_managed=cluster.runtime.operator_managed,
        runtime_mutation_mode=cluster.runtime.mutation_mode,
        runtime_rest_access=cluster.runtime.rest_access,
        runtime_kubernetes_context=cluster.runtime.kubernetes_context,
        runtime_kubernetes_namespace=cluster.runtime.kubernetes_namespace,
        runtime_service=cluster.runtime.service,
        runtime_pod_selector=cluster.runtime.pod_selector,
        runtime_resource_name=cluster.runtime.resource_name,
        runtime_connector_label_selector=cluster.runtime.connector_label_selector,
        runtime_provider=cluster.runtime.provider,
        runtime_limitations=cluster.runtime.limitations,
        kafka_bootstrap_servers=kafka_bootstrap_servers,
        kafka_hosts=tuple(
            _bootstrap_host(server) for server in kafka_bootstrap_servers
        ),
        kafka_security_protocol=kafka.security_protocol if kafka else None,
        kafka_sasl_mechanism=kafka.sasl_mechanism if kafka else None,
        kafka_iam_region=kafka.iam_region if kafka else None,
        kafka_aws_profile=kafka.aws_profile if kafka else None,
        kafka_bootstrap_source=kafka_bootstrap_source,
        schema_registry_urls=schema_registry_urls,
        schema_registry_source=schema_registry_source,
        render_prune_config_keys=prune_keys,
        render_vars=render_vars,
        notes=tuple(notes),
    )


def _cluster_group_effective_value(
    args: argparse.Namespace, value: str
) -> EffectiveValue:
    # The CLI also accepts `--cluster` as an alias. Some command trees reuse
    # the same option name with a different dest, so we check raw option names
    # too instead of relying only on explicit dest tracking.
    explicit_options = set(getattr(args, "_explicit_options", ()) or ())
    explicit = was_explicit(args, "cluster_group") or bool(
        explicit_options.intersection({"--cluster-group", "--cluster"})
    )
    return EffectiveValue(name="cluster_group", value=value, implicit=not explicit)


def _connect_host(url: str) -> str:
    parsed = urlparse(str(url))
    return parsed.netloc or str(url)


def _bootstrap_host(server: str) -> str:
    value = str(server).strip()
    if value.startswith("[") and "]" in value:
        return value[1 : value.index("]")]
    if value.count(":") == 1:
        return value.rsplit(":", 1)[0]
    return value


def _blocked_source(message: str, *, blocked: str) -> str | None:
    return blocked if blocked in message else None


def _inventory_note(message: str, *, default: str) -> str:
    if "worker-managed/pruned" in message:
        return "Kafka bootstrap is pruned by cluster render rules"
    if "Schema Registry config is pruned" in message:
        return "Schema Registry is pruned by cluster render rules"
    return default


def _result_to_payload(result: ConfigClustersResult) -> Dict[str, Any]:
    clusters = [_cluster_to_payload(cluster) for cluster in result.clusters]
    env_count = sum(len(cluster.envs) for cluster in result.clusters)
    return {
        "config_path": str(result.config_path),
        "default_cluster": result.default_cluster,
        "cluster_count": len(result.clusters),
        "env_scope_count": env_count,
        "clusters": clusters,
    }


def _cluster_to_payload(cluster: ConfigClusterInventory) -> Dict[str, Any]:
    return {
        "name": cluster.name,
        "is_default": cluster.is_default,
        "envs": [_env_to_payload(env) for env in cluster.envs],
    }


def _env_to_payload(env: ConfigClusterEnvInventory) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "env": env.env.value,
        "runtime": {
            "type": env.runtime_type,
            "operator_managed": env.runtime_operator_managed,
            "mutation_mode": env.runtime_mutation_mode,
            "rest_access": env.runtime_rest_access,
            "kubernetes_context": env.runtime_kubernetes_context,
            "kubernetes_namespace": env.runtime_kubernetes_namespace,
            "service": env.runtime_service,
            "pod_selector": env.runtime_pod_selector,
            "resource_name": env.runtime_resource_name,
            "connector_label_selector": env.runtime_connector_label_selector,
            "provider": env.runtime_provider,
            "limitations": list(env.runtime_limitations),
        },
        "connect_urls": list(env.connect_urls),
        "connect_hosts": list(env.connect_hosts),
        "lifecycle": env.lifecycle.to_meta(),
        "kafka_bootstrap_servers": list(env.kafka_bootstrap_servers),
        "kafka_hosts": list(env.kafka_hosts),
        "schema_registry_urls": list(env.schema_registry_urls),
        "kafka_bootstrap_source": env.kafka_bootstrap_source,
        "schema_registry_source": env.schema_registry_source,
        "notes": list(env.notes),
        "render_prune_config_keys": list(env.render_prune_config_keys),
    }
    kafka_auth = {
        "security_protocol": env.kafka_security_protocol,
        "sasl_mechanism": env.kafka_sasl_mechanism,
        "iam_region": env.kafka_iam_region,
        "aws_profile": env.kafka_aws_profile,
    }
    kafka_auth = {key: value for key, value in kafka_auth.items() if value}
    if kafka_auth:
        payload["kafka_auth"] = kafka_auth
    if env.render_vars is not None:
        payload["render_vars"] = env.render_vars
    return payload


__all__ = ["ConfigClustersService"]
