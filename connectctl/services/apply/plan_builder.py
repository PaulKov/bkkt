from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from ...git import diff_name_status, get_head_sha, guess_base_sha
from ...logging_utils import get_logger
from ...models import Environment
from ...planning import Planner
from ...repo import ConnectorRepo, LayerResolver
from ...repo.apply_targets import ApplyItem, resolve_apply_targets
from ...git_changes import expand_renames
from ...cli_helpers.templates import _print_template_expansions


@dataclass(frozen=True)
class ApplyPlan:
    env: Environment
    apply_items: List[ApplyItem]
    delete_rels: List[Path]
    base_ref: Optional[str] = None
    head_ref: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        return not self.apply_items and not self.delete_rels


def build_apply_plan(
    *,
    args: Any,
    env: Environment,
    repo_root: Path,
    repo: ConnectorRepo,
    repo_config: Any,
    logger=None,
) -> ApplyPlan:
    """Build apply plan based on --changed or explicit paths.

    Returns a list of ApplyItem(s) to render+apply and a list of deleted relpaths
    (when --changed is enabled).
    """

    log = get_logger(logger)

    apply_items: List[ApplyItem] = []
    delete_rels: List[Path] = []

    if bool(getattr(args, "changed", False)):
        base = getattr(args, "base", None) or guess_base_sha()
        head = getattr(args, "head", None) or get_head_sha()

        changes = diff_name_status(base, head, repo_root=repo_root)
        changes = expand_renames(changes)

        planner = Planner(repo=repo, layer_resolver=LayerResolver(repo_config))
        plan = planner.plan(env=env, changes=changes, repo_root=repo_root)

        env_files = list(plan.to_apply)
        apply_items = [
            ApplyItem(
                actual_path=p.resolve(),
                requested_path=p.resolve(),
                runtime_vars={},
                runtime_var_sources={},
                is_virtual=False,
            )
            for p in env_files
        ]
        delete_rels = list(plan.to_delete_paths)

        log.info(
            "Computed plan for env=%s from git diff %s..%s: apply=%s delete=%s",
            env.value,
            base,
            head,
            len(env_files),
            len(delete_rels),
        )

        return ApplyPlan(
            env=env,
            apply_items=apply_items,
            delete_rels=delete_rels,
            base_ref=base,
            head_ref=head,
        )

    # Explicit paths passed (files, dirs, or globs)
    targets = resolve_apply_targets(
        raw_paths=getattr(args, "paths", []) or [],
        env=env,
        repo_root=repo_root,
        repo=repo,
        expand_templates=bool(getattr(args, "expand_templates", False)),
    )
    apply_items = list(targets.items)

    # Helpful hints for template resolutions and directory expansions.
    for requested, actual in targets.template_mappings:
        try:
            req_rel = requested.relative_to(repo_root)
        except Exception:
            req_rel = requested
        try:
            act_rel = actual.relative_to(repo_root)
        except Exception:
            act_rel = actual
        log.info("Resolved template: %s -> %s", req_rel, act_rel)

    if bool(getattr(args, "expand_templates", False)):
        _print_template_expansions(targets, repo_root, logger=log)

    return ApplyPlan(env=env, apply_items=apply_items, delete_rels=[])
