from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class KubernetesPodInfo:
    name: str
    phase: str
    labels: dict[str, str]


@dataclass(frozen=True)
class KubernetesServiceInfo:
    name: str
    namespace: str
    ports: tuple[int, ...]


class KubernetesApi(Protocol):
    """Small Kubernetes inventory port used by Connect runtime adapters."""

    def list_pods(
        self,
        *,
        namespace: str,
        label_selector: str | None = None,
    ) -> Sequence[KubernetesPodInfo]: ...

    def get_service(
        self,
        *,
        namespace: str,
        name: str,
    ) -> KubernetesServiceInfo | None: ...
