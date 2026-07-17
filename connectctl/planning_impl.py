from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Set

from .git import ChangedPath
from .models import Environment, Plan
from .planning_matchers import env_remainder, match_base_file, match_env_file
from .planning_scope import infer_override_scope, scope_matches
from .repo import ConnectorRepo, LayerResolver


class Planner:
    """Compute which connectors must be applied / deleted based on git diff."""

    def __init__(self, repo: ConnectorRepo, layer_resolver: LayerResolver):
        self.repo = repo
        self.layers = layer_resolver

    def plan(
        self, env: Environment, changes: Sequence[ChangedPath], repo_root: Path
    ) -> Plan:
        current_env_files = list(self.repo.iter_deployable_connector_files(env=env))
        infos = {p: self.repo.parse_connector_path(p) for p in current_env_files}

        to_apply: Set[Path] = set()
        to_delete: Set[Path] = set()

        fs = getattr(self.repo, "fs", None)

        def _exists(p: Path) -> bool:
            return fs.exists(p) if fs else p.exists()

        # Helper: index by connector_dir for base files
        by_parent: dict[Path, List[Path]] = {}
        for p in current_env_files:
            by_parent.setdefault(p.parent, []).append(p)

        for ch in changes:
            rel = ch.path
            # Skip irrelevant dirs early (connectctl code, tests, etc.).
            # NOTE: __global is NOT ignored here because changes there must trigger redeploys.
            ignored_for_changes = set(self.repo.cfg.ignore_dirs) - {"__global"}
            if any(part in ignored_for_changes for part in rel.parts):
                continue

            abs_path = (repo_root / rel).resolve()

            # 1) Deleted env-specific connector file => desired-state delete
            me = match_env_file(rel.name)
            if ch.status.startswith("D") and me:
                if me[0] == env:
                    to_delete.add(rel)
                continue

            # 2) Base file changed => apply related env files
            bm = match_base_file(rel.name)
            if bm:
                remainder_with_ext = bm.group(1) + ".json"
                parent = abs_path.parent
                for env_file in by_parent.get(parent, []):
                    rem = env_remainder(env_file.name)
                    if rem and rem.lower() == remainder_with_ext.lower():
                        to_apply.add(env_file)
                continue

            # 3) Direct change to env connector file => apply it (if in target env)
            me = match_env_file(rel.name)
            if me and _exists(abs_path):
                if me[0] == env:
                    to_apply.add(abs_path)
                continue

            # 4) Any override file at supported layer paths => apply all connectors in that scope.
            if rel.name in {"all.json", "dev.json", "stage.json", "prod.json"}:
                scope = infer_override_scope(rel)
                for p, info in infos.items():
                    if scope_matches(info, env, scope):
                        to_apply.add(p)
                continue

        return Plan(
            env=env,
            to_apply=tuple(sorted(to_apply)),
            to_delete_paths=tuple(sorted(to_delete)),
        )
