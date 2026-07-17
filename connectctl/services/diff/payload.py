from __future__ import annotations

from typing import Any, Dict, Iterable, List

from ...app.context import ConnectTarget
from ...models import Environment

from .models import DisabledItem, DriftItem, MissingItem


def build_diff_payload(
    *,
    env: Environment,
    targets_by_cluster: Dict[str, ConnectTarget],
    cluster_stats: Dict[str, Dict[str, int]],
    manifests_checked: int,
    clean: int,
    disabled: List[DisabledItem],
    missing: List[MissingItem],
    drifted: Iterable[DriftItem],
) -> Dict[str, Any]:
    """Сформировать машинный payload для diff.

    В single-cluster режиме сохраняем поле `cluster` для обратной совместимости.
    В multi-cluster режиме добавляем `clusters` с деталями по каждому cluster group.
    """

    drifted_list = list(drifted)

    clusters_payload: Dict[str, Any] = {}
    for cluster_name, target in targets_by_cluster.items():
        st = cluster_stats.get(cluster_name, {})
        clusters_payload[cluster_name] = {
            "cluster": {
                "group": target.cluster.name,
                "env": target.cluster.env.value,
                "urls": list(target.cluster.urls),
            },
            "counts": {
                "manifests_checked": int(st.get("checked", 0)),
                "in_sync": int(st.get("clean", 0)),
                "drifted": int(st.get("drifted", 0)),
                "missing": int(st.get("missing", 0)),
            },
            "lifecycle": {
                "disabled_skipped": int(st.get("disabled", 0)),
            },
            "disabled": [
                {
                    "name": item.name,
                    "cluster": item.cluster,
                    "manifest": item.manifest_rel,
                    "reason": item.reason,
                    "ticket": item.ticket,
                    "until": item.until,
                }
                for item in disabled
                if item.cluster == cluster_name
            ],
            "missing": sorted([m.name for m in missing if m.cluster == cluster_name]),
            "drift": [
                {
                    "name": item.name,
                    "cluster": item.cluster,
                    "manifest": item.manifest_rel,
                    "pruned_config_keys": list(item.pruned_config_keys),
                    "diff_keys": list(item.diff_keys),
                    "trimmed": item.trimmed,
                    "diff": item.diff,
                }
                for item in drifted_list
                if item.cluster == cluster_name
            ],
        }

    payload: Dict[str, Any] = {
        "command": "diff",
        "env": env.value,
        "comparison_mode": "post_prune",
        "mode": "multi" if len(clusters_payload) > 1 else "single",
        "counts": {
            "manifests_checked": int(manifests_checked),
            "in_sync": int(clean),
            "drifted": int(len(drifted_list)),
            "missing": int(len(missing)),
        },
        "lifecycle": {
            "disabled_skipped": int(len(disabled)),
        },
        "clusters": clusters_payload,
        "disabled": [
            {
                "name": item.name,
                "cluster": item.cluster,
                "manifest": item.manifest_rel,
                "reason": item.reason,
                "ticket": item.ticket,
                "until": item.until,
            }
            for item in sorted(disabled, key=lambda x: (x.cluster, x.name))
        ],
        "missing": [
            {"name": m.name, "cluster": m.cluster}
            for m in sorted(missing, key=lambda x: (x.cluster, x.name))
        ],
        "drift": [
            {
                "name": item.name,
                "cluster": item.cluster,
                "manifest": item.manifest_rel,
                "pruned_config_keys": list(item.pruned_config_keys),
                "diff_keys": list(item.diff_keys),
                "trimmed": item.trimmed,
                "diff": item.diff,
            }
            for item in drifted_list
        ],
    }

    if len(clusters_payload) == 1:
        only = next(iter(clusters_payload.values()))
        payload["cluster"] = only["cluster"]

    return payload
