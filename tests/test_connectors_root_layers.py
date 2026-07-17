from __future__ import annotations

import json
from pathlib import Path

from connectctl.models import RepoConfig
from connectctl.rendering.renderer_impl import ConnectorRenderer
from connectctl.repo import ConnectorRepo, LayerResolver


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_renderer_uses_connector_layers_under_connectors_root(tmp_path: Path) -> None:
    repo_root = tmp_path
    connectors_root = repo_root / "connectors"
    cfg = RepoConfig(root=repo_root, connectors_root=connectors_root, ignore_dirs=())

    _write_json(repo_root / "__global/all.json", {"config": {"global_key": "1"}})
    connector_all = connectors_root / "demo/sink/iceberg/connector_demo__ds/all.json"
    _write_json(
        connector_all,
        {
            "vars": {"custom": "ok"},
            "config": {"from_connector": "${custom}"},
        },
    )
    env_file = (
        connectors_root
        / "demo/sink/iceberg/connector_demo__ds/prod.demo.ds.sink.raw.iceberg.0.json"
    )
    _write_json(env_file, {"config": {"from_env": "1"}})

    repo = ConnectorRepo(cfg)
    renderer = ConnectorRenderer(repo=repo, layers=LayerResolver(cfg))

    rr = renderer.render(env_file)

    assert rr.manifest.config["global_key"] == "1"
    assert rr.manifest.config["from_connector"] == "ok"
    assert rr.manifest.config["from_env"] == "1"
    assert connector_all.resolve() in rr.layers


def test_parse_connector_path_detects_custom_mode_under_connectors_root(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    connectors_root = repo_root / "connectors"
    cfg = RepoConfig(root=repo_root, connectors_root=connectors_root, ignore_dirs=())

    _write_json(
        connectors_root / "demo/source/postgres/modes/backfill/all.json",
        {"config": {"snapshot.mode": "never"}},
    )
    env_file = (
        connectors_root
        / "demo/source/postgres/connector_demo__ds/prod.demo.ds.source.postgres.backfill.0.json"
    )
    _write_json(env_file, {})

    repo = ConnectorRepo(cfg)
    info = repo.parse_connector_path(env_file)

    assert info.mode == "backfill"


def test_parse_connector_path_detects_sink_variant_under_connectors_root(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    connectors_root = repo_root / "connectors"
    cfg = RepoConfig(root=repo_root, connectors_root=connectors_root, ignore_dirs=())

    _write_json(
        connectors_root / "demo/sink/iceberg/types/events/all.json",
        {"config": {"transforms.route.type": "events"}},
    )
    env_file = (
        connectors_root
        / "demo/sink/iceberg/connector_demo__ds/prod_sink_ods_demo__ds__events.json"
    )
    _write_json(env_file, {})

    repo = ConnectorRepo(cfg)
    info = repo.parse_connector_path(env_file)

    assert info.variant == "events"


def test_parse_connector_path_detects_dot_style_sink_variant_after_system(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    connectors_root = repo_root / "connectors"
    cfg = RepoConfig(root=repo_root, connectors_root=connectors_root, ignore_dirs=())

    _write_json(
        connectors_root / "demo/sink/iceberg/types/events/all.json",
        {"config": {"transforms.setTableName.table.suffix": "events"}},
    )
    env_file = (
        connectors_root
        / "demo/sink/iceberg/connector_demo__ds/prod.demo.ds.sink.raw.iceberg.dbt.events.0.json"
    )
    _write_json(env_file, {})

    repo = ConnectorRepo(cfg)
    info = repo.parse_connector_path(env_file)

    assert info.variant == "events"


def test_parse_connector_path_keeps_raw_when_dot_style_tail_is_not_a_kind(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    connectors_root = repo_root / "connectors"
    cfg = RepoConfig(root=repo_root, connectors_root=connectors_root, ignore_dirs=())

    _write_json(
        connectors_root / "demo/sink/iceberg/types/events/all.json",
        {"config": {"transforms.setTableName.table.suffix": "events"}},
    )
    env_file = (
        connectors_root
        / "demo/sink/iceberg/connector_demo__ds/prod.demo.ds.sink.raw.iceberg.user_balance_histories.dbt.0.json"
    )
    _write_json(env_file, {})

    repo = ConnectorRepo(cfg)
    info = repo.parse_connector_path(env_file)

    assert info.variant == "raw"


def test_renderer_uses_dot_style_sink_kind_overlays_after_system(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    connectors_root = repo_root / "connectors"
    cfg = RepoConfig(root=repo_root, connectors_root=connectors_root, ignore_dirs=())

    _write_json(
        repo_root / "__global/sink/iceberg/types/events/all.json",
        {"config": {"transforms.setTableName.db.name": "demo__db"}},
    )
    _write_json(
        connectors_root / "demo/sink/iceberg/connector_demo__ds/types/events/all.json",
        {"config": {"transforms.setTableName.table.suffix": "events"}},
    )
    env_file = (
        connectors_root
        / "demo/sink/iceberg/connector_demo__ds/prod.demo.ds.sink.raw.iceberg.dbt.events.0.json"
    )
    _write_json(
        env_file,
        {
            "name": "prod.demo.ds.sink.raw.iceberg.dbt.events.0",
            "config": {
                "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
                "transforms": "setTableName",
            },
        },
    )

    repo = ConnectorRepo(cfg)
    renderer = ConnectorRenderer(repo=repo, layers=LayerResolver(cfg))

    rr = renderer.render(env_file)

    assert rr.manifest.config["transforms.setTableName.db.name"] == "demo__db"
    assert rr.manifest.config["transforms.setTableName.table.suffix"] == "events"
