from __future__ import annotations

import json
from pathlib import Path

from connectctl.models import Environment, RepoConfig
from connectctl.repo.apply_targets import resolve_apply_targets
from connectctl.repo.scanner import ConnectorRepo


def _write_json(p: Path, obj: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def test_apply_directory_collects_deployable_env_manifests(tmp_path: Path):
    # layout
    repo_root = tmp_path
    cfg = RepoConfig(root=repo_root, connectors_root=repo_root)
    repo = ConnectorRepo(cfg)

    # deployable manifest
    _write_json(
        repo_root
        / "acme/source/postgres/connector_x/prod.acme.x.source.postgres.0.json",
        {"name": "prod.acme.x.source.postgres.0"},
    )
    # env overrides (should be ignored by directory scan)
    _write_json(
        repo_root / "acme/source/postgres/connector_x/prod.json",
        {"vars": {"index": "0"}},
    )

    targets = resolve_apply_targets(
        raw_paths=["acme/source/postgres/connector_x/"],
        env=Environment.prod,
        repo_root=repo_root,
        repo=repo,
        expand_templates=False,
    )
    assert len(targets.items) == 1
    assert targets.items[0].actual_path.name == "prod.acme.x.source.postgres.0.json"
    assert targets.items[0].requested_path.name == "prod.acme.x.source.postgres.0.json"


def test_expand_templates_maps_instance_filename_to_template(tmp_path: Path):
    repo_root = tmp_path
    cfg = RepoConfig(root=repo_root, connectors_root=repo_root)
    repo = ConnectorRepo(cfg)

    base_dir = repo_root / "acme/sink/iceberg/connector_y"
    # nearest env vars (still supported, but instances are preferred)
    _write_json(base_dir / "prod.json", {"vars": {"index": ["1"]}})
    # template file exists
    _write_json(
        base_dir / "prod.acme.y.sink.iceberg.${index}.json",
        {"name": "prod.acme.y.sink.iceberg.${index}"},
    )

    requested = "acme/sink/iceberg/connector_y/prod.acme.y.sink.iceberg.1.json"
    targets = resolve_apply_targets(
        raw_paths=[requested],
        env=Environment.prod,
        repo_root=repo_root,
        repo=repo,
        expand_templates=True,
    )
    assert len(targets.items) == 1
    assert targets.items[0].actual_path.name == "prod.acme.y.sink.iceberg.${index}.json"
    assert targets.items[0].requested_path.name == "prod.acme.y.sink.iceberg.1.json"
    assert targets.items[0].runtime_vars.get("index") == "1"
    assert targets.template_mappings, "expected template mapping"


def test_expand_templates_directory_uses_instances_and_skips_existing(tmp_path: Path):
    repo_root = tmp_path
    cfg = RepoConfig(root=repo_root, connectors_root=repo_root)
    repo = ConnectorRepo(cfg)

    base_dir = repo_root / "acme/source/postgres/connector_z"
    # Template file
    _write_json(
        base_dir / "prod.acme.z.source.postgres.${index}.json",
        {"name": "prod.acme.z.source.postgres.${index}"},
    )
    # Instances file has 1 and 2
    _write_json(
        base_dir / "prod.instances.json",
        {"instances": [{"index": "1"}, {"index": "2"}]},
    )
    # Real file exists for 1 -> should skip virtual 1.json
    _write_json(
        base_dir / "prod.acme.z.source.postgres.1.json",
        {"name": "prod.acme.z.source.postgres.1"},
    )

    targets = resolve_apply_targets(
        raw_paths=["acme/source/postgres/connector_z/"],
        env=Environment.prod,
        repo_root=repo_root,
        repo=repo,
        expand_templates=True,
    )

    requested_names = sorted([it.requested_path.name for it in targets.items])
    assert "prod.acme.z.source.postgres.1.json" in requested_names
    assert "prod.acme.z.source.postgres.2.json" in requested_names
    # Ensure 2 is virtual from template
    v2 = [it for it in targets.items if it.requested_path.name.endswith(".2.json")][0]
    assert v2.is_virtual
    assert v2.actual_path.name.endswith("${index}.json")


def test_expand_templates_requested_instance_extracts_index(tmp_path: Path):
    repo_root = tmp_path
    cfg = RepoConfig(root=repo_root, connectors_root=repo_root)
    repo = ConnectorRepo(cfg)

    base_dir = repo_root / "acme/sink/iceberg/connector_y"
    _write_json(
        base_dir / "prod.acme.y.sink.iceberg.${index}.json",
        {"name": "prod.acme.y.sink.iceberg.${index}"},
    )

    requested = "acme/sink/iceberg/connector_y/prod.acme.y.sink.iceberg.7.json"
    targets = resolve_apply_targets(
        raw_paths=[requested],
        env=Environment.prod,
        repo_root=repo_root,
        repo=repo,
        expand_templates=True,
    )
    assert len(targets.items) == 1
    it = targets.items[0]
    assert it.actual_path.name.endswith("${index}.json")
    assert it.requested_path.name.endswith(".7.json")
    assert it.runtime_vars.get("index") == "7"
