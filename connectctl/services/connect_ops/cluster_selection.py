from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ...exceptions import ConfigError
from ...models import Environment
from ...settings_clusters_lifecycle import disabled_cluster_message


def is_all_cluster_token(value: object) -> bool:
    """Return true when a CLI cluster value means all cluster groups."""

    return str(value or "").strip().lower() in {"all", "*"}


@dataclass(frozen=True)
class ConnectClusterSelection:
    """Validated Connect cluster selection for one environment."""

    env: Environment
    cluster_groups: tuple[str, ...]
    requested: str | None
    requested_all: bool

    @property
    def is_fanout(self) -> bool:
        return len(self.cluster_groups) > 1 or self.requested_all


class ConnectClusterSelectionResolver:
    """Resolve `--cluster <name>|all|*` to deterministic cluster groups."""

    def resolve(
        self,
        *,
        env: Environment,
        cluster_arg: str | None,
        default_cluster: str | None,
        available_cluster_groups: Iterable[str],
        settings,
    ) -> ConnectClusterSelection:
        available = tuple(sorted(str(item) for item in available_cluster_groups))
        if not available:
            raise ConfigError("No Kafka Connect cluster groups are configured")

        requested = str(cluster_arg).strip() if cluster_arg is not None else None
        if requested and is_all_cluster_token(requested):
            disabled_messages: list[str] = []
            selected_groups: list[str] = []
            for group in available:
                cluster = settings.cluster_groups.get(group, {}).get(env)
                if cluster is None:
                    continue
                lifecycle = getattr(cluster, "lifecycle", None)
                if lifecycle is not None and getattr(lifecycle, "disabled", False):
                    disabled_messages.append(
                        disabled_cluster_message(
                            cluster=group,
                            env=env.value,
                            lifecycle=lifecycle,
                        )
                    )
                    continue
                selected_groups.append(group)
            cluster_groups = tuple(selected_groups)
            if not cluster_groups:
                suffix = (
                    " Disabled scopes: " + "; ".join(disabled_messages)
                    if disabled_messages
                    else ""
                )
                raise ConfigError(
                    f"--cluster all selected no enabled live targets for env={env.value}.{suffix}"
                )
            return ConnectClusterSelection(
                env=env,
                cluster_groups=cluster_groups,
                requested=requested,
                requested_all=True,
            )

        cluster_group = requested or default_cluster or "default"
        if cluster_group not in set(available):
            raise ConfigError(
                f"Unknown Kafka Connect cluster group: {cluster_group!r}. "
                f"Available: {', '.join(available)}"
            )
        if env not in settings.cluster_groups.get(cluster_group, {}):
            raise ConfigError(
                f"Cluster group {cluster_group!r} has no env={env.value} configuration"
            )
        cluster = settings.cluster_groups[cluster_group][env]
        lifecycle = getattr(cluster, "lifecycle", None)
        if lifecycle is not None and getattr(lifecycle, "disabled", False):
            raise ConfigError(
                disabled_cluster_message(
                    cluster=cluster_group,
                    env=env.value,
                    lifecycle=lifecycle,
                )
            )

        return ConnectClusterSelection(
            env=env,
            cluster_groups=(cluster_group,),
            requested=requested,
            requested_all=False,
        )


__all__ = [
    "ConnectClusterSelection",
    "ConnectClusterSelectionResolver",
    "is_all_cluster_token",
]
