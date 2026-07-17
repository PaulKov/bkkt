from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...app.context import ConnectTarget
from ...cli_helpers.live_scopes import LiveScope, dedupe_live_scopes
from ...logging_utils import get_logger
from ...models import Environment
from .cluster_selection import ConnectClusterSelection, ConnectClusterSelectionResolver


@dataclass(frozen=True)
class ConnectExecutionTarget:
    """One physical Kafka Connect target plus logical aliases."""

    target: ConnectTarget
    aliases: tuple[dict[str, object], ...]

    @property
    def cluster_group(self) -> str:
        return self.target.cluster.name

    @property
    def env(self) -> str:
        return self.target.env.value


@dataclass(frozen=True)
class ConnectExecutionPlan:
    """Resolved target plan for a `bkkt connect ...` command."""

    selection: ConnectClusterSelection
    targets: tuple[ConnectExecutionTarget, ...]

    @property
    def is_fanout(self) -> bool:
        return self.selection.is_fanout


class ConnectTargetExecutor:
    """Resolve and materialize Connect targets for command execution."""

    def __init__(self, *, ctx: Any, logger=None) -> None:
        self._ctx = ctx
        self._log = get_logger(logger or getattr(ctx, "logger", None))
        self._selection_resolver = ConnectClusterSelectionResolver()

    def resolve_plan(
        self,
        *,
        env_arg: str,
        cluster_arg: str | None,
        throttle=None,
        timeout=None,
        print_banners: bool = True,
    ) -> ConnectExecutionPlan:
        env = self._ctx.env(env_arg)
        selection = self._selection_resolver.resolve(
            env=env,
            cluster_arg=cluster_arg,
            default_cluster=self._ctx.settings.default_cluster,
            available_cluster_groups=self._ctx.settings.cluster_groups.keys(),
            settings=self._ctx.settings,
        )
        if selection.is_fanout:
            targets = self._resolve_fanout_targets(
                selection=selection,
                throttle=throttle,
                timeout=timeout,
                print_banners=print_banners,
            )
        else:
            targets = (
                self._resolve_single_target(
                    env=env,
                    cluster_group=selection.cluster_groups[0],
                    throttle=throttle,
                    timeout=timeout,
                    print_banner=print_banners,
                ),
            )
        return ConnectExecutionPlan(selection=selection, targets=targets)

    def _resolve_single_target(
        self,
        *,
        env: Environment,
        cluster_group: str,
        throttle,
        timeout,
        print_banner: bool,
    ) -> ConnectExecutionTarget:
        target = self._connect_target(
            env,
            cluster_group,
            throttle=throttle,
            timeout=timeout,
        )
        if print_banner:
            self._print_banner(target)
        return ConnectExecutionTarget(
            target=target,
            aliases=(
                {
                    "cluster": target.cluster.name,
                    "env": target.env.value,
                    "urls": list(target.cluster.urls),
                },
            ),
        )

    def _resolve_fanout_targets(
        self,
        *,
        selection: ConnectClusterSelection,
        throttle,
        timeout,
        print_banners: bool,
    ) -> tuple[ConnectExecutionTarget, ...]:
        scopes = dedupe_live_scopes(
            settings=self._ctx.settings,
            envs=(selection.env.value,),
            cluster_groups=selection.cluster_groups,
        )
        return tuple(
            self._target_from_scope(
                scope,
                throttle=throttle,
                timeout=timeout,
                print_banner=print_banners,
            )
            for scope in scopes
        )

    def _target_from_scope(
        self,
        scope: LiveScope,
        *,
        throttle,
        timeout,
        print_banner: bool,
    ) -> ConnectExecutionTarget:
        target = self._connect_target(
            scope.primary_env,
            scope.primary_cluster,
            throttle=throttle,
            timeout=timeout,
        )
        if print_banner:
            self._print_banner(target)
        return ConnectExecutionTarget(
            target=target,
            aliases=tuple(
                {
                    "cluster": alias.cluster,
                    "env": alias.env,
                    "urls": list(alias.urls),
                }
                for alias in scope.aliases
            ),
        )

    def _print_banner(self, target: ConnectTarget) -> None:
        printer = getattr(self._ctx, "print_cluster_banner", None)
        if callable(printer):
            printer(target)
        else:
            self._log.info(
                "# BKKT: cluster=%s env=%s urls=%s",
                target.cluster.name,
                target.env.value,
                ",".join(target.cluster.urls),
            )

    def _connect_target(
        self,
        env: Environment,
        cluster_group: str,
        *,
        throttle,
        timeout,
    ) -> ConnectTarget:
        target_factory = getattr(self._ctx, "connect_target", None)
        if callable(target_factory):
            return target_factory(
                env,
                cluster_group,
                throttle=throttle,
                timeout=timeout,
            )

        cluster = self._ctx.resolve_cluster(env, cluster_group)
        client_factory = getattr(self._ctx, "connect_client")
        try:
            client = client_factory(
                env,
                cluster_group,
                throttle=throttle,
                timeout=timeout,
            )
        except TypeError:
            client = client_factory(env, cluster_group, throttle=throttle)
        return ConnectTarget(env=env, cluster=cluster, client=client)


__all__ = [
    "ConnectExecutionPlan",
    "ConnectExecutionTarget",
    "ConnectTargetExecutor",
]
