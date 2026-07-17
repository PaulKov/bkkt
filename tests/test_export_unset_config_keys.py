from __future__ import annotations

import json
from pathlib import Path

from connectctl.export.layout import DetectedLayout
from connectctl.export.planner_export import export_connector_to_repo
from connectctl.models import ConnectorType, Environment, RepoConfig
from connectctl.repo import ConnectorRepo


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_export_reuse_overrides_writes_unset_keys_instead_of_config_null(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    _write_json(
        repo_root / "__global/sink/iceberg/types/events/all.json",
        {
            "config": {
                "inherited.absent": "from-global",
                "transforms.unwrap.type": "io.example.Unwrap",
            }
        },
    )
    repo = ConnectorRepo(
        RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    )
    name = "prod.demo.ds.sink.raw.iceberg.cdc.events.dbt.0"
    layout = DetectedLayout(
        env=Environment.prod,
        domain="demo",
        connector_type=ConnectorType.sink,
        system="iceberg",
        connector_dir="connector_demo__ds",
        dataset="ds",
        layer="raw",
        kind="events",
    )

    written, _layers = export_connector_to_repo(
        repo=repo,
        connector_name=name,
        remote_config={
            "connector.class": "io.example.SinkConnector",
            "topics": "demo.topic",
        },
        layout=layout,
        dry_run=False,
        force=True,
        reuse_overrides=True,
        iceberg_generate_overrides=False,
        iceberg_generate_manifests=False,
        save_diffs=True,
    )

    env_override = (
        repo_root / "demo/sink/iceberg/connector_demo__ds/prod.json"
    ).resolve()
    assert env_override in written
    payload = json.loads(env_override.read_text(encoding="utf-8"))

    assert payload["bkkt"]["unset_config_keys"] == [
        "inherited.absent",
        "transforms.unwrap.type",
    ]
    assert payload.get("config", {}) == {
        "connector.class": "io.example.SinkConnector",
        "topics": "demo.topic",
    }
    assert all(value is not None for value in payload.get("config", {}).values())

    report_path = (
        repo_root
        / "demo/sink/iceberg/connector_demo__ds/export"
        / f"export__{name}__1.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["diffs"]["inherited.absent"]["resolution"] == (
        "accepted_unset_inherited_key"
    )
