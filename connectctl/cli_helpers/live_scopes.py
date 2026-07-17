from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from ..models import Environment
from ..services.connector_facts import ConnectorScopeAlias


@dataclass(frozen=True)
class LiveScope:
    urls: Tuple[str, ...]
    aliases: Tuple[ConnectorScopeAlias, ...]

    @property
    def primary_env(self) -> Environment:
        return Environment.from_str(self.aliases[0].env)

    @property
    def primary_cluster(self) -> str:
        return self.aliases[0].cluster


def dedupe_live_scopes(
    *,
    settings,
    envs: Iterable[str],
    cluster_groups: Iterable[str],
) -> List[LiveScope]:
    deduped: Dict[Tuple[str, ...], List[ConnectorScopeAlias]] = {}
    for env_value in envs:
        env = Environment.from_str(env_value)
        for cluster_group in cluster_groups:
            env_map = settings.cluster_groups.get(cluster_group)
            if not env_map:
                continue
            cluster = env_map.get(env)
            if cluster is None:
                continue
            lifecycle = getattr(cluster, "lifecycle", None)
            if lifecycle is not None and getattr(lifecycle, "disabled", False):
                continue
            urls = tuple(
                sorted(str(url).strip() for url in cluster.urls if str(url).strip())
            )
            if not urls:
                continue
            deduped.setdefault(urls, []).append(
                ConnectorScopeAlias(
                    env=env.value,
                    cluster=cluster_group,
                    urls=urls,
                )
            )

    scopes: List[LiveScope] = []
    for urls, aliases in deduped.items():
        sorted_aliases = tuple(
            sorted(aliases, key=lambda item: (item.env, item.cluster))
        )
        scopes.append(LiveScope(urls=urls, aliases=sorted_aliases))

    scopes.sort(
        key=lambda scope: (
            scope.aliases[0].env,
            scope.aliases[0].cluster,
            scope.urls,
        )
    )
    return scopes


__all__ = ["LiveScope", "dedupe_live_scopes"]
