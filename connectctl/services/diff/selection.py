from __future__ import annotations

from pathlib import Path
from typing import List

from ...git import diff_name_status, get_head_sha, guess_base_sha
from ...git_changes import expand_renames
from ...models import Environment
from ...planning import Planner
from ...repo import ConnectorRepo, LayerResolver


def select_env_files(
    args,
    *,
    env: Environment,
    repo_root: Path,
    repo: ConnectorRepo,
    layer_resolver: LayerResolver,
) -> List[Path]:
    """Выбрать список env-манифестов для diff.

    Приоритет:
      1) --changed
      2) явные paths
      3) весь env
    """

    if bool(getattr(args, "changed", False)):
        base = getattr(args, "base", None) or guess_base_sha()
        head = getattr(args, "head", None) or get_head_sha()
        changes = diff_name_status(base, head, repo_root=repo_root)
        changes = expand_renames(changes)

        planner = Planner(repo=repo, layer_resolver=layer_resolver)
        plan = planner.plan(env=env, changes=changes, repo_root=repo_root)
        return list(plan.to_apply)

    raw_paths = list(getattr(args, "paths", []) or [])
    if raw_paths:
        return [(repo_root / p).resolve() for p in raw_paths]

    return repo.list_env_manifests(env)
