from __future__ import annotations

from dataclasses import dataclass

from .models import ConnectClusterConfig


@dataclass(frozen=True)
class RoutingDecision:
    cluster_name: str
    cluster: ConnectClusterConfig
    # Where the final cluster selection came from (useful for logs/debug).
    source: str
