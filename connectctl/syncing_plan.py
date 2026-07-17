from __future__ import annotations

import re
from typing import List, Sequence

from .models import ConnectorManifest, Environment
from .syncing_models import SyncPlan


def _expand_env_placeholders(pattern: str, env: Environment) -> str:
    """Expand simple placeholders inside regex patterns.

    Supported placeholders:
      - {env} -> env.value

    This keeps sync policies concise in connectctl.yaml, e.g.
      allow_regexes: ["^{env}\\."]
    """

    return str(pattern).replace("{env}", env.value)


def _matches_any(regexes: Sequence[str], name: str) -> bool:
    return any(re.match(r, name) for r in regexes)


def compute_sync_plan(
    *,
    env: Environment,
    desired: Sequence[ConnectorManifest],
    existing_names: Sequence[str],
    protected_names: Sequence[str] = (),
    keep_name_regexes: Sequence[str] = (),
    prune: bool = False,
    allow_names: Sequence[str] = (),
    deny_names: Sequence[str] = (),
    allow_regexes: Sequence[str] = (),
    deny_regexes: Sequence[str] = (),
) -> SyncPlan:
    # Expand simple placeholders in regex policies (e.g. "^{env}\\.").
    keep_name_regexes = [_expand_env_placeholders(r, env) for r in keep_name_regexes]
    allow_regexes = [_expand_env_placeholders(r, env) for r in allow_regexes]
    deny_regexes = [_expand_env_placeholders(r, env) for r in deny_regexes]

    desired_map = {m.name: m for m in desired}
    desired_names = sorted(desired_map.keys())
    existing_names = sorted(existing_names)
    protected_names = tuple(sorted(set(protected_names)))

    to_apply = desired_names

    to_delete: List[str] = []
    if prune:
        # Candidates: those existing not in desired and not matching keep regex.
        for n in existing_names:
            if n in desired_map:
                continue
            if n in protected_names:
                continue
            if _matches_any(keep_name_regexes, n):
                continue
            to_delete.append(n)

        # Apply allow/deny policy
        def _allowed(name: str) -> bool:
            # allow_names or allow_regexes = allow list. If empty, allow by default.
            allow_ok = True
            if allow_names or allow_regexes:
                allow_ok = name in allow_names or _matches_any(allow_regexes, name)
            deny_ok = True
            if deny_names or deny_regexes:
                deny_ok = not (name in deny_names or _matches_any(deny_regexes, name))
            return allow_ok and deny_ok

        to_delete = [n for n in to_delete if _allowed(n)]

    return SyncPlan(
        env=env,
        desired=desired_map,
        desired_names=desired_names,
        existing_names=existing_names,
        protected_names=protected_names,
        to_apply=tuple(to_apply),
        to_delete=tuple(sorted(to_delete)),
    )
