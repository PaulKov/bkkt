from __future__ import annotations

import json
import logging
from pathlib import Path

from connectctl.adapters.filesystem import InMemoryFileSystem
from connectctl.export.planner_io import apply_plan_to_repo
from connectctl.models import RepoConfig
from connectctl.models import Environment
from connectctl.rendering.renderer_impl import ConnectorRenderer
from connectctl.repo.layers import LayerResolver
from connectctl.repo.apply_targets import resolve_apply_targets
from connectctl.repo.scanner_repo import ConnectorRepo
from connectctl.services.init.models import InitOptions
from connectctl.services.init.scaffold import scaffold_repo_files


def test_inmemory_fs_apply_plan_to_repo_writes_files() -> None:
    fs = InMemoryFileSystem()
    plan = {
        Path("/repo/a.json"): {"b": 1},
        Path("/repo/sub/c.json"): {"x": True, "y": [1, 2, 3]},
    }

    written = apply_plan_to_repo(plan, dry_run=False, force=False, fs=fs)

    assert Path("/repo/a.json") in written
    assert Path("/repo/sub/c.json") in written

    assert fs.exists(Path("/repo/a.json"))
    assert fs.exists(Path("/repo/sub/c.json"))

    raw = fs.read_text(Path("/repo/a.json"), encoding="utf-8")
    assert raw.endswith("\n")
    assert json.loads(raw) == {"b": 1}


def test_inmemory_fs_init_scaffold_creates_expected_layout() -> None:
    fs = InMemoryFileSystem()
    repo_root = Path("/repo")

    target_dir = Path("/repo/domain/source/postgres/connector_domain__dataset")

    opts = InitOptions(
        repo_root=repo_root,
        target_dir=target_dir,
        fs=fs,
        templates_root=repo_root / "__init_templates",
        template_overrides=[],
        domain="domain",
        connector_type="source",
        system="postgres",
        dataset="dataset",
        connector_dir="connector_domain__dataset",
        envs=["dev"],
        layer=None,
        index=0,
        modes=["init", "cdc"],
        kinds=[None],
        modes_explicit=True,
        kinds_explicit=False,
        explicit_name=None,
        name_template=None,
        create_all=True,
        init_only=True,
        force=False,
        dry_run=False,
    )

    scaffold_repo_files(opts=opts, log=logging.getLogger("test"))

    assert fs.exists(target_dir / "all.json")
    assert fs.exists(target_dir / "dev.json")

    dev_env = json.loads(fs.read_text(target_dir / "dev.json"))
    assert dev_env["vars"]["db"]["secret"] == "dbz-${domain}-${env}"
    assert (
        dev_env["config"]["database.hostname"] == "${secretManager:${db.secret}:host}"
    )
    assert fs.exists(target_dir / "modes/init/all.json")
    assert fs.exists(target_dir / "modes/init/dev.json")

    assert fs.exists(target_dir / "modes/cdc/all.json")
    assert fs.exists(target_dir / "modes/cdc/dev.json")

    init_all = json.loads(fs.read_text(target_dir / "modes/init/all.json"))
    assert init_all["vars"]["debezium_snapshot_mode_init"] == "initial_only"

    cdc_all = json.loads(fs.read_text(target_dir / "modes/cdc/all.json"))
    assert cdc_all["vars"]["debezium_snapshot_mode_cdc"] == "no_data"

    assert fs.exists(target_dir / "dev.domain.dataset.source.postgres.init.0.json")
    assert fs.exists(target_dir / "dev.domain.dataset.source.postgres.cdc.0.json")


def test_inmemory_fs_init_scaffold_sink_kinds_creates_type_overlays() -> None:
    fs = InMemoryFileSystem()
    repo_root = Path("/repo")

    target_dir = Path("/repo/domain/sink/iceberg/connector_domain__dataset")

    opts = InitOptions(
        repo_root=repo_root,
        target_dir=target_dir,
        fs=fs,
        templates_root=repo_root / "__init_templates",
        template_overrides=[],
        domain="domain",
        connector_type="sink",
        system="iceberg",
        dataset="dataset",
        connector_dir="connector_domain__dataset",
        envs=["prod"],
        layer="raw",
        index=0,
        modes=[None],
        kinds=["events", "flatten"],
        modes_explicit=False,
        kinds_explicit=True,
        explicit_name=None,
        name_template=None,
        create_all=True,
        init_only=False,
        force=False,
        dry_run=False,
    )

    scaffold_repo_files(opts=opts, log=logging.getLogger("test"))

    assert fs.exists(target_dir / "all.json")
    assert fs.exists(target_dir / "prod.json")

    assert fs.exists(target_dir / "types/events/all.json")
    assert fs.exists(target_dir / "types/events/prod.json")

    assert fs.exists(target_dir / "types/flatten/all.json")
    assert fs.exists(target_dir / "types/flatten/prod.json")

    assert fs.exists(
        target_dir / "prod.domain.dataset.sink.raw.iceberg.cdc.events.0.json"
    )
    assert fs.exists(
        target_dir / "prod.domain.dataset.sink.raw.iceberg.cdc.flatten.0.json"
    )


def test_inmemory_fs_init_scaffold_clickhouse_sink_uses_clickhouse_defaults() -> None:
    fs = InMemoryFileSystem()
    repo_root = Path("/repo")

    target_dir = Path("/repo/acme/sink/clickhouse/connector_acme__events")

    opts = InitOptions(
        repo_root=repo_root,
        target_dir=target_dir,
        fs=fs,
        templates_root=repo_root / "__init_templates",
        template_overrides=[],
        domain="acme",
        connector_type="sink",
        system="clickhouse",
        dataset="events",
        connector_dir="connector_acme__events",
        envs=["stage"],
        layer="raw",
        index=0,
        modes=[None],
        kinds=[None],
        modes_explicit=False,
        kinds_explicit=False,
        explicit_name=None,
        name_template=None,
        create_all=True,
        init_only=False,
        force=False,
        dry_run=False,
    )

    scaffold_repo_files(opts=opts, log=logging.getLogger("test"))

    all_json = json.loads(fs.read_text(target_dir / "all.json"))
    stage_json = json.loads(fs.read_text(target_dir / "stage.json"))

    assert all_json["config"]["connector.class"] == (
        "com.clickhouse.kafka.connect.ClickHouseSinkConnector"
    )
    assert all_json["config"]["topic2TableMap"] == "CHANGE_ME_TOPIC=change_me_raw"
    assert "iceberg" not in all_json["vars"]
    assert stage_json["vars"]["clickhouse"]["secret"] == "stage/${domain}/clickhouse"
    assert stage_json["config"]["hostname"] == (
        "${secretManager:${clickhouse.secret}:host}"
    )
    assert fs.exists(target_dir / "stage.acme.events.sink.raw.clickhouse.0.json")


def test_inmemory_fs_renderer_can_render_without_disk() -> None:
    fs = InMemoryFileSystem()
    repo_root = Path("/repo")

    cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())

    # Layers
    fs.write_text(Path("/repo/__global/all.json"), json.dumps({"a": "1"}) + "\n")
    fs.write_text(Path("/repo/demo/all.json"), json.dumps({"b": "2"}) + "\n")

    env_file = Path(
        "/repo/demo/source/postgres/connector_demo__ds/prod.demo.ds.source.postgres.cdc.0.json"
    )
    fs.write_text(env_file, "{}\n")

    repo = ConnectorRepo(cfg, fs=fs)
    layers = LayerResolver(cfg, fs=fs)
    renderer = ConnectorRenderer(repo=repo, layers=layers)

    rr = renderer.render(env_file)

    assert rr.manifest.name == env_file.stem
    assert rr.manifest.config["a"] == "1"
    assert rr.manifest.config["b"] == "2"


def test_inmemory_fs_apply_targets_can_scan_directory_without_disk() -> None:
    fs = InMemoryFileSystem()
    repo_root = Path("/repo")

    cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    env_file = Path(
        "/repo/demo/source/postgres/connector_demo__ds/prod.demo.ds.source.postgres.cdc.0.json"
    )
    fs.write_text(env_file, "{}\n")

    repo = ConnectorRepo(cfg, fs=fs)

    targets = resolve_apply_targets(
        raw_paths=[str(env_file.parent)],
        env=Environment.prod,
        repo_root=repo_root,
        repo=repo,
        expand_templates=False,
    )

    assert len(targets.items) == 1
    assert targets.items[0].actual_path == env_file.resolve()


def test_inmemory_fs_export_virtual_render_can_read_overrides_without_disk() -> None:
    """Проверяем, что export-virtual render читает слои через FileSystem (а не Path.read_text())."""

    from connectctl.export.virtual_render import render_virtual

    fs = InMemoryFileSystem()
    repo_root = Path("/repo")

    cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())

    # Global override layer
    fs.write_text(Path("/repo/__global/all.json"), json.dumps({"a": "1"}) + "\n")

    env_file = Path(
        "/repo/demo/source/postgres/connector_demo__ds/prod.demo.ds.source.postgres.cdc.0.json"
    )

    repo = ConnectorRepo(cfg, fs=fs)

    planned_files = {
        env_file: {
            "name": env_file.stem,
            "config": {"b": "2"},
        }
    }

    name, config, layers_used = render_virtual(
        repo=repo, env_file=env_file, planned_files=planned_files
    )

    assert name == env_file.stem
    assert config["a"] == "1"
    assert config["b"] == "2"

    assert Path("/repo/__global/all.json") in layers_used
