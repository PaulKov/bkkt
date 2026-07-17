from __future__ import annotations

from .models import ConnectClusterConfig


def format_cluster_target(cluster: ConnectClusterConfig) -> str:
    urls = ", ".join(cluster.urls)
    return f"{cluster.name}/{cluster.env.value} ({urls})"
