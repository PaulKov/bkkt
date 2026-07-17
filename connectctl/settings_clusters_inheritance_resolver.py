from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence, Tuple

from .exceptions import ConfigError
from .models import ClusterLifecycle, Environment
from .settings_clusters_lifecycle import (
    ClusterLifecycleOverride,
    apply_effective_lifecycle,
)

from .settings_clusters_inheritance_parse import (
    FROM_FUNC_NAME,
    parse_from_cluster_group_env_call,
)
from .settings_clusters_inheritance_select import select_from_mapping


class ClusterGroupEnvResolver:
    """Резолвит from_cluster_group_env(...) внутри секции clusters."""

    def __init__(
        self,
        raw_groups: Mapping[str, Mapping[Environment, Any]],
        *,
        group_lifecycles: Mapping[str, ClusterLifecycle] | None = None,
        root_overrides: Sequence[ClusterLifecycleOverride] = (),
    ):
        self._raw_groups: Dict[str, Dict[Environment, Any]] = {
            str(g): dict(env_map) for g, env_map in raw_groups.items()
        }
        self._group_lifecycles: Dict[str, ClusterLifecycle] = {
            str(group): lifecycle
            for group, lifecycle in (group_lifecycles or {}).items()
        }
        self._root_overrides = tuple(root_overrides)
        self._cache: Dict[Tuple[str, Environment], Any] = {}

    def resolve_env_mapping(self, group: str, *, env: Environment) -> Mapping[str, Any]:
        resolved = self._resolve_env_mapping(group, env=env, stack=())
        if not isinstance(resolved, Mapping):
            raise ConfigError(
                f"clusters.{group}.{env.value}: {FROM_FUNC_NAME}(... ) must resolve to a mapping at env level"
            )
        return resolved

    def _resolve_obj(
        self, obj: Any, *, env: Environment, stack: Tuple[Tuple[str, Environment], ...]
    ) -> Any:
        if isinstance(obj, str):
            call = parse_from_cluster_group_env_call(obj)
            if call is None:
                return obj
            ref_group, selector = call
            base_env_cfg = self._resolve_env_mapping(ref_group, env=env, stack=stack)
            if not isinstance(base_env_cfg, Mapping):
                raise ConfigError(
                    f"clusters.{ref_group}.{env.value} resolved to non-mapping"
                )
            return select_from_mapping(base_env_cfg, selector)

        if isinstance(obj, Mapping):
            out: Dict[str, Any] = {}
            for k, v in obj.items():
                out[str(k)] = self._resolve_obj(v, env=env, stack=stack)
            return out

        if isinstance(obj, list):
            return [self._resolve_obj(x, env=env, stack=stack) for x in obj]

        return obj

    def _resolve_env_mapping(
        self,
        group: str,
        *,
        env: Environment,
        stack: Tuple[Tuple[str, Environment], ...],
    ) -> Any:
        key = (group, env)
        if key in self._cache:
            return self._cache[key]

        if key in stack:
            chain = " -> ".join(
                [f"{g}.{e.value}" for g, e in stack] + [f"{group}.{env.value}"]
            )
            raise ConfigError(f"Cycle detected in {FROM_FUNC_NAME}(): {chain}")

        if group not in self._raw_groups:
            raise ConfigError(
                f"Unknown cluster group '{group}' referenced by {FROM_FUNC_NAME}()"
            )

        if env not in self._raw_groups[group]:
            raise ConfigError(f"clusters.{group} does not define env '{env.value}'")

        raw_val = self._raw_groups[group][env]
        stack2 = stack + (key,)

        if isinstance(raw_val, str):
            call = parse_from_cluster_group_env_call(raw_val)
            if call is None:
                raise ConfigError(
                    f"clusters.{group}.{env.value} must be a mapping or {FROM_FUNC_NAME}(...)"
                )
            ref_group, selector = call
            base_env_cfg = self._resolve_env_mapping(ref_group, env=env, stack=stack2)
            if not isinstance(base_env_cfg, Mapping):
                raise ConfigError(
                    f"clusters.{ref_group}.{env.value} resolved to non-mapping"
                )
            resolved = select_from_mapping(base_env_cfg, selector)

        elif isinstance(raw_val, Mapping):
            resolved = self._resolve_obj(raw_val, env=env, stack=stack2)

        else:
            raise ConfigError(
                f"clusters.{group}.{env.value} must be a mapping or {FROM_FUNC_NAME}(...)"
            )

        if isinstance(resolved, Mapping):
            resolved = apply_effective_lifecycle(
                resolved,
                group_lifecycle=self._group_lifecycles.get(group, ClusterLifecycle()),
                root_overrides=self._root_overrides,
                cluster=group,
                env=env.value,
            )

        self._cache[key] = resolved
        return resolved
