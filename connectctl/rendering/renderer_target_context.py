from __future__ import annotations

from typing import Any, Dict, Mapping

from ..models import ConnectClusterConfig


def build_target_context(cluster: ConnectClusterConfig) -> Dict[str, Any]:
    render_vars: Mapping[str, Any] = cluster.render_vars or {}
    namespace = str(render_vars.get("server_id_namespace") or cluster.name or "default")
    return {
        "target": {
            "cluster": {
                "name": cluster.name,
                "env": cluster.env.value,
                "server_id_namespace": namespace,
            }
        }
    }
