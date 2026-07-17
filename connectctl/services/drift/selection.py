from __future__ import annotations

from pathlib import Path
from typing import List

from ...app.context import CliContext
from ...git import diff_name_status, get_head_sha, guess_base_sha
from ...models import Environment
from ...planning import Planner
from ...repo import ConnectorRepo, LayerResolver

from ...git_changes import expand_renames


def select_manifest_paths(
    *, ctx: CliContext, args, env: Environment, repo: ConnectorRepo
) -> List[Path]:
    """Select env manifest paths for drift.

    Supported selection modes:
    - --changed: uses git diff base/head and Planner (like apply/diff).
    - positional paths: explicit subset.
    - otherwise: all env manifests.
    """

    repo_root = ctx.repo_root
    settings = ctx.settings

    if bool(getattr(args, "changed", False)):
        base = getattr(args, "base", None) or guess_base_sha()
        head = getattr(args, "head", None) or get_head_sha()
        changes = diff_name_status(base, head, repo_root=repo_root)
        changes = expand_renames(changes)

        planner = Planner(
            repo=repo, layer_resolver=LayerResolver(settings.repo, fs=ctx.fs)
        )
        plan = planner.plan(env=env, changes=changes, repo_root=repo_root)
        return list(plan.to_apply)

    raw_paths = list(getattr(args, "paths", []) or [])
    if raw_paths:
        return [(repo_root / p).resolve() for p in raw_paths]

    return repo.list_env_manifests(env)
