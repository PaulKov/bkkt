from __future__ import annotations

from typing import Any, Mapping, Sequence

from .exceptions import ConfigError
from .models import ConnectRuntimeConfig

_SUPPORTED_RUNTIME_TYPES = {
    "static_hosts",
    "k8s_rest",
    "strimzi",
    "confluent_kubernetes",
    "managed_connect",
}


def parse_connect_runtime(
    connect_cfg: Mapping[str, Any],
    *,
    cluster_name: str,
    env_name: str,
    legacy_urls: Sequence[str],
) -> tuple[ConnectRuntimeConfig, Sequence[str]]:
    """Parse Kafka Connect runtime metadata for one cluster/env scope.

    The historical `connect.hosts` shape is treated as an explicit
    `static_hosts` runtime. Kubernetes/operator runtimes may still expose REST
    URLs for diagnostics, but the runtime metadata decides whether REST writes
    are allowed.
    """

    runtime_obj = connect_cfg.get("runtime")
    if runtime_obj is None:
        return ConnectRuntimeConfig(), legacy_urls
    if not isinstance(runtime_obj, Mapping):
        raise ConfigError(
            f"{_prefix(cluster_name, env_name)}.runtime must be a mapping"
        )

    runtime_type = str(runtime_obj.get("type") or "static_hosts").strip()
    if runtime_type not in _SUPPORTED_RUNTIME_TYPES:
        raise ConfigError(
            f"{_prefix(cluster_name, env_name)}.runtime.type={runtime_type!r} is not supported. "
            f"Expected one of: {', '.join(sorted(_SUPPORTED_RUNTIME_TYPES))}"
        )

    if runtime_type == "static_hosts":
        return _static_hosts_runtime(runtime_obj, legacy_urls=legacy_urls)
    if runtime_type == "k8s_rest":
        return _k8s_rest_runtime(runtime_obj)
    if runtime_type == "strimzi":
        return _strimzi_runtime(runtime_obj)
    if runtime_type == "confluent_kubernetes":
        return _confluent_kubernetes_runtime(runtime_obj)
    return _managed_connect_runtime(runtime_obj)


def _static_hosts_runtime(
    runtime_obj: Mapping[str, Any], *, legacy_urls: Sequence[str]
) -> tuple[ConnectRuntimeConfig, Sequence[str]]:
    rest_obj = _mapping(runtime_obj.get("rest"))
    rest_access = str(rest_obj.get("access") or "direct")
    runtime = ConnectRuntimeConfig(
        type="static_hosts",
        operator_managed=False,
        mutation_mode=str(runtime_obj.get("mutation_mode") or "rest"),
        rest_access=rest_access,
        limitations=(),
    )
    return runtime, legacy_urls


def _k8s_rest_runtime(
    runtime_obj: Mapping[str, Any],
) -> tuple[ConnectRuntimeConfig, tuple[str, ...]]:
    kubernetes = _mapping(runtime_obj.get("kubernetes"))
    rest = _mapping(runtime_obj.get("rest"))
    rest_access = str(rest.get("access") or "port_forward")
    service = _string_or_none(rest.get("service") or kubernetes.get("service"))
    pod_selector = _string_or_none(rest.get("pod_selector") or rest.get("podSelector"))
    port = _optional_int(rest.get("port"), default=8083)
    local_port = _optional_int(rest.get("local_port") or rest.get("localPort"))
    namespace = _string_or_none(kubernetes.get("namespace"))
    runtime = ConnectRuntimeConfig(
        type="k8s_rest",
        operator_managed=False,
        mutation_mode=str(runtime_obj.get("mutation_mode") or "rest"),
        rest_access=rest_access,
        kubernetes_context=_string_or_none(kubernetes.get("context")),
        kubernetes_namespace=namespace,
        service=service,
        pod_selector=pod_selector,
        port=port,
        local_port=local_port,
        limitations=_k8s_limitations(rest_access),
    )
    return runtime, _rest_urls(
        rest,
        access=rest_access,
        service=service,
        namespace=namespace,
        port=port,
        local_port=local_port,
    )


def _strimzi_runtime(
    runtime_obj: Mapping[str, Any],
) -> tuple[ConnectRuntimeConfig, tuple[str, ...]]:
    kubernetes = _mapping(runtime_obj.get("kubernetes"))
    strimzi = _mapping(runtime_obj.get("strimzi"))
    rest = _mapping(runtime_obj.get("rest"))
    rest_access = str(rest.get("access") or "port_forward")
    service = _string_or_none(rest.get("service"))
    namespace = _string_or_none(kubernetes.get("namespace"))
    port = _optional_int(rest.get("port"), default=8083)
    local_port = _optional_int(rest.get("local_port") or rest.get("localPort"))
    runtime = ConnectRuntimeConfig(
        type="strimzi",
        operator_managed=True,
        mutation_mode=str(runtime_obj.get("mutation_mode") or "crd"),
        rest_access=rest_access,
        kubernetes_context=_string_or_none(kubernetes.get("context")),
        kubernetes_namespace=namespace,
        service=service,
        pod_selector=_string_or_none(
            rest.get("pod_selector") or rest.get("podSelector")
        ),
        port=port,
        local_port=local_port,
        resource_name=_string_or_none(
            strimzi.get("kafka_connect_name") or strimzi.get("kafkaConnectName")
        ),
        connector_label_selector=_string_or_none(
            strimzi.get("connector_label_selector")
            or strimzi.get("connectorLabelSelector")
        ),
        limitations=(
            "REST mutations are disabled by default; mutate KafkaConnector CRDs.",
        ),
    )
    return runtime, _rest_urls(
        rest,
        access=rest_access,
        service=service,
        namespace=namespace,
        port=port,
        local_port=local_port,
    )


def _confluent_kubernetes_runtime(
    runtime_obj: Mapping[str, Any],
) -> tuple[ConnectRuntimeConfig, tuple[str, ...]]:
    kubernetes = _mapping(runtime_obj.get("kubernetes"))
    cfk = _mapping(runtime_obj.get("confluent_kubernetes") or runtime_obj.get("cfk"))
    rest = _mapping(runtime_obj.get("rest"))
    rest_access = str(rest.get("access") or "port_forward")
    service = _string_or_none(rest.get("service"))
    namespace = _string_or_none(kubernetes.get("namespace"))
    port = _optional_int(rest.get("port"), default=8083)
    local_port = _optional_int(rest.get("local_port") or rest.get("localPort"))
    runtime = ConnectRuntimeConfig(
        type="confluent_kubernetes",
        operator_managed=True,
        mutation_mode=str(runtime_obj.get("mutation_mode") or "crd"),
        rest_access=rest_access,
        kubernetes_context=_string_or_none(kubernetes.get("context")),
        kubernetes_namespace=namespace,
        service=service,
        pod_selector=_string_or_none(
            rest.get("pod_selector") or rest.get("podSelector")
        ),
        port=port,
        local_port=local_port,
        resource_name=_string_or_none(
            cfk.get("connect_name") or cfk.get("connectName")
        ),
        connector_label_selector=_string_or_none(
            cfk.get("connector_label_selector") or cfk.get("connectorLabelSelector")
        ),
        limitations=(
            "REST mutations are disabled by default; mutate CFK Connector CRDs.",
        ),
    )
    return runtime, _rest_urls(
        rest,
        access=rest_access,
        service=service,
        namespace=namespace,
        port=port,
        local_port=local_port,
    )


def _managed_connect_runtime(
    runtime_obj: Mapping[str, Any],
) -> tuple[ConnectRuntimeConfig, tuple[str, ...]]:
    rest = _mapping(runtime_obj.get("rest"))
    runtime = ConnectRuntimeConfig(
        type="managed_connect",
        operator_managed=True,
        mutation_mode=str(runtime_obj.get("mutation_mode") or "read_only"),
        rest_access=str(rest.get("access") or "provider_api"),
        provider=_string_or_none(runtime_obj.get("provider")),
        resource_name=_string_or_none(runtime_obj.get("name")),
        limitations=("Managed Connect runtime is read-only in this BKKT release.",),
    )
    return runtime, ()


def _rest_urls(
    rest: Mapping[str, Any],
    *,
    access: str,
    service: str | None,
    namespace: str | None,
    port: int | None,
    local_port: int | None,
) -> tuple[str, ...]:
    configured = _string_list(rest.get("urls") or rest.get("url"))
    if configured:
        return tuple(configured)
    scheme = str(rest.get("scheme") or "http")
    if access == "port_forward":
        if local_port:
            return (f"{scheme}://127.0.0.1:{local_port}",)
        return ()
    if access in {"direct", "service", "in_cluster"} and service:
        host = service
        if access == "in_cluster" and namespace:
            host = f"{service}.{namespace}.svc"
        return (f"{scheme}://{host}:{port or 8083}",)
    return ()


def _k8s_limitations(rest_access: str) -> tuple[str, ...]:
    if rest_access == "port_forward":
        return ("REST requires a local kubectl port-forward session.",)
    if rest_access in {"disabled", "none"}:
        return ("REST endpoint is not configured for this runtime.",)
    return ()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _optional_int(value: Any, *, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    return int(value)


def _prefix(cluster_name: str, env_name: str) -> str:
    return f"clusters.{cluster_name}.{env_name}.connect"
