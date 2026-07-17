import json
from pathlib import Path

from connectctl.git import ChangedPath
from connectctl.models import Environment, RepoConfig
from connectctl.planning import Planner
from connectctl.repo import ConnectorRepo, LayerResolver


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj) + "\n", encoding="utf-8")


def test_planner_scope_domain_type(tmp_path: Path):
    repo_root = tmp_path

    # Two connectors in domain a/source/postgres and one in domain b/source/mysql
    c1 = repo_root / "a/source/postgres/connector_a/dev_source_a__x.json"
    c2 = repo_root / "a/source/postgres/connector_a/dev_source_a__y.json"
    c3 = repo_root / "b/source/mysql/connector_b/dev_source_b__z.json"
    for p in [c1, c2, c3]:
        _write_json(p, {"name": p.stem, "config": {"connector.class": "X"}})

    # Change: domain a source override
    changed = [ChangedPath(status="M", path=Path("a/source/all.json"))]

    cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    repo = ConnectorRepo(cfg)
    planner = Planner(repo=repo, layer_resolver=LayerResolver(cfg))

    plan = planner.plan(env=Environment.dev, changes=changed, repo_root=repo_root)

    # Should redeploy both a/source/... connectors, but not b/source
    apply_rel = {p.relative_to(repo_root).as_posix() for p in plan.to_apply}
    assert "a/source/postgres/connector_a/dev_source_a__x.json" in apply_rel
    assert "a/source/postgres/connector_a/dev_source_a__y.json" in apply_rel
    assert "b/source/mysql/connector_b/dev_source_b__z.json" not in apply_rel
