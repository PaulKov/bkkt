from __future__ import annotations

from typing import Any, Sequence

from ..exceptions import ConfigError
from ..ports.kubernetes_api import (
    KubernetesApi,
    KubernetesPodInfo,
    KubernetesServiceInfo,
)


class KubernetesClient(KubernetesApi):
    """Official Kubernetes Python client adapter.

    The dependency is optional (`bkkt[kubernetes]`) and imported lazily so
    static-host users do not need Kubernetes packages installed.
    """

    def __init__(self, *, context: str | None = None, in_cluster: bool = False):
        try:
            from kubernetes import client, config
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ConfigError(
                "Kubernetes runtime checks require the optional dependency: "
                "`pip install 'bkkt[kubernetes]'` or `uv sync --extra kubernetes`."
            ) from exc

        if in_cluster:
            config.load_incluster_config()
        else:
            config.load_kube_config(context=context)
        self._core = client.CoreV1Api()

    def list_pods(
        self,
        *,
        namespace: str,
        label_selector: str | None = None,
    ) -> Sequence[KubernetesPodInfo]:
        response = self._core.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector,
        )
        return tuple(_pod_info(item) for item in response.items)

    def get_service(
        self,
        *,
        namespace: str,
        name: str,
    ) -> KubernetesServiceInfo | None:
        try:
            response = self._core.read_namespaced_service(
                namespace=namespace,
                name=name,
            )
        except Exception as exc:  # pragma: no cover - client-specific ApiException
            if getattr(exc, "status", None) == 404:
                return None
            raise
        ports = tuple(
            int(port.port)
            for port in getattr(getattr(response, "spec", None), "ports", []) or []
            if getattr(port, "port", None) is not None
        )
        return KubernetesServiceInfo(name=name, namespace=namespace, ports=ports)


def _pod_info(item: Any) -> KubernetesPodInfo:
    metadata = getattr(item, "metadata", None)
    status = getattr(item, "status", None)
    return KubernetesPodInfo(
        name=str(getattr(metadata, "name", "") or ""),
        phase=str(getattr(status, "phase", "") or "UNKNOWN"),
        labels=dict(getattr(metadata, "labels", None) or {}),
    )
