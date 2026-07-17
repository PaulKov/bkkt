from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Set

from ...exceptions import ConfigError
from ...models import Environment

_ENV_ORDER = {
    Environment.dev: 0,
    Environment.stage: 1,
    Environment.prod: 2,
}


def split_csv_values(values: Optional[Sequence[str]]) -> List[str]:
    """Parse argparse append values that may also contain comma-separated items."""

    if not values:
        return []
    out: List[str] = []
    for value in values:
        if value is None:
            continue
        for part in str(value).split(","):
            item = part.strip()
            if item:
                out.append(item)
    return out


def parse_env_filter(values: Optional[Sequence[str]]) -> Optional[Set[Environment]]:
    parts = split_csv_values(values)
    if not parts:
        return None
    envs: Set[Environment] = set()
    for part in parts:
        envs.add(Environment.from_str(part.lower()))
    return envs


def parse_cluster_group_filter(
    values: Optional[Sequence[str]],
) -> Optional[Set[str]]:
    parts = split_csv_values(values)
    if not parts:
        return None
    return {str(part).strip() for part in parts if str(part).strip()}


def select_cluster_groups(
    all_groups: Iterable[str], *, include: Optional[Set[str]]
) -> List[str]:
    groups = sorted(set(all_groups))
    if not include:
        return groups

    missing = sorted(group for group in include if group not in groups)
    if missing:
        raise ConfigError(f"Unknown cluster group(s): {missing}. Available: {groups}")

    return [group for group in groups if group in include]


def select_envs(
    all_envs: Iterable[Environment], *, include: Optional[Set[Environment]]
) -> List[Environment]:
    envs = sorted(set(all_envs), key=_env_sort_key)
    if not include:
        return envs

    missing = sorted((env for env in include if env not in envs), key=_env_sort_key)
    if missing:
        raise ConfigError(
            f"Config does not define env(s): {[env.value for env in missing]} "
            f"in this scope. Available: {[env.value for env in envs]}"
        )

    return [env for env in envs if env in include]


def render_env_filter(env_filter: Optional[Set[Environment]]) -> str:
    if not env_filter:
        return "all"
    return ",".join(env.value for env in sorted(env_filter, key=_env_sort_key))


def render_cluster_group_filter(group_filter: Optional[Set[str]]) -> str:
    if not group_filter:
        return "all"
    return ",".join(sorted(group_filter))


def _env_sort_key(env: Environment) -> tuple[int, str]:
    return (_ENV_ORDER.get(env, 99), env.value)


__all__ = [
    "parse_cluster_group_filter",
    "parse_env_filter",
    "render_cluster_group_filter",
    "render_env_filter",
    "select_cluster_groups",
    "select_envs",
    "split_csv_values",
]
