import json
from pathlib import Path

import pytest

from connectctl.exporting import (
    DetectedLayout,
    build_sink_manifest_filename,
    resolve_sink_export_collision,
)
from connectctl.models import ConnectorType, Environment, RepoConfig
from connectctl.repo import ConnectorRepo
from connectctl.exceptions import ConfigError


def _make_repo(tmp_path: Path) -> ConnectorRepo:
    cfg = RepoConfig(root=tmp_path, connectors_root=tmp_path)
    return ConnectorRepo(cfg)


def test_export_collision_auto_suffixes_connector_dir(tmp_path: Path):
    repo = _make_repo(tmp_path)
    layout = DetectedLayout(
        env=Environment.prod,
        domain="user_finance",
        connector_type=ConnectorType.sink,
        system="iceberg",
        connector_dir="connector_user_finance__finops_casino",
        dataset="finops_casino",
        layer="ods",
        kind="default",
    )
    base_dir = tmp_path / "user_finance" / "sink" / "iceberg" / layout.connector_dir
    base_dir.mkdir(parents=True, exist_ok=True)
    export_name = "prod.user_finance.finops_casino.sink.ods.iceberg.1"
    env_file = base_dir / build_sink_manifest_filename(layout, export_name)
    env_file.write_text(
        json.dumps(
            {
                "name": "prod.user_finance.finops_casino.sink.ods.iceberg.0",
                "config": {},
            },
            indent=2,
        )
        + "\n"
    )

    layout2, info = resolve_sink_export_collision(
        repo=repo,
        layout=layout,
        connector_name=export_name,
        force=False,
        enabled=True,
    )
    assert layout2.connector_dir == "connector_user_finance__finops_casino__1"
    assert info and info.get("collision") is True


def test_export_collision_disabled_keeps_layout(tmp_path: Path):
    repo = _make_repo(tmp_path)
    layout = DetectedLayout(
        env=Environment.prod,
        domain="user_finance",
        connector_type=ConnectorType.sink,
        system="iceberg",
        connector_dir="connector_user_finance__finops_casino",
        dataset="finops_casino",
        layer="ods",
        kind="default",
    )
    base_dir = tmp_path / "user_finance" / "sink" / "iceberg" / layout.connector_dir
    base_dir.mkdir(parents=True, exist_ok=True)
    export_name = "prod.user_finance.finops_casino.sink.ods.iceberg.1"
    (base_dir / build_sink_manifest_filename(layout, export_name)).write_text(
        json.dumps({"name": "other", "config": {}}, indent=2) + "\n"
    )

    layout2, info = resolve_sink_export_collision(
        repo=repo,
        layout=layout,
        connector_name=export_name,
        force=False,
        enabled=False,
    )
    assert layout2.connector_dir == layout.connector_dir
    assert info and info.get("collision") is True


def test_export_collision_same_name_is_not_a_collision(tmp_path: Path):
    repo = _make_repo(tmp_path)
    layout = DetectedLayout(
        env=Environment.prod,
        domain="user_finance",
        connector_type=ConnectorType.sink,
        system="iceberg",
        connector_dir="connector_user_finance__finops_casino",
        dataset="finops_casino",
        layer="ods",
        kind="default",
    )
    base_dir = tmp_path / "user_finance" / "sink" / "iceberg" / layout.connector_dir
    base_dir.mkdir(parents=True, exist_ok=True)
    same = "prod.user_finance.finops_casino.sink.ods.iceberg.1"
    (base_dir / build_sink_manifest_filename(layout, same)).write_text(
        json.dumps({"name": same, "config": {}}, indent=2) + "\n"
    )

    layout2, info = resolve_sink_export_collision(
        repo=repo,
        layout=layout,
        connector_name=same,
        force=False,
        enabled=True,
    )
    assert layout2.connector_dir == layout.connector_dir
    assert info is None


def test_export_collision_without_index_raises(tmp_path: Path):
    repo = _make_repo(tmp_path)
    layout = DetectedLayout(
        env=Environment.prod,
        domain="user_finance",
        connector_type=ConnectorType.sink,
        system="iceberg",
        connector_dir="connector_user_finance__finops_casino",
        dataset="finops_casino",
        layer="ods",
        kind="default",
    )
    base_dir = tmp_path / "user_finance" / "sink" / "iceberg" / layout.connector_dir
    base_dir.mkdir(parents=True, exist_ok=True)
    export_name = "prod.user_finance.finops_casino.sink.ods.iceberg"
    (base_dir / build_sink_manifest_filename(layout, export_name)).write_text(
        json.dumps({"name": "other", "config": {}}, indent=2) + "\n"
    )

    with pytest.raises(ConfigError):
        resolve_sink_export_collision(
            repo=repo,
            layout=layout,
            connector_name="prod.user_finance.finops_casino.sink.ods.iceberg",  # no .<index>
            force=False,
            enabled=True,
        )
