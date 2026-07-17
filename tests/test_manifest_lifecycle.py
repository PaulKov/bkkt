from __future__ import annotations

import json
from pathlib import Path

import pytest

from connectctl.adapters.filesystem import LocalFileSystem
from connectctl.config_models import NamingConfig, SafetyConfig, SyncConfig
from connectctl.exceptions import RenderError
from connectctl.models import ConnectClusterConfig, Environment, RepoConfig
from connectctl.rendering.factory import build_renderer
from connectctl.settings_models import (
    ExportConfig,
    Settings,
    TagSettings,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _settings(repo_root: Path) -> Settings:
    repo_cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    cluster = ConnectClusterConfig(
        env=Environment.prod,
        urls=("http://prod.main:8083",),
        kafka=None,
        name="acme-main",
    )
    return Settings(
        repo=repo_cfg,
        clusters={Environment.prod: cluster},
        cluster_groups={"acme-main": {Environment.prod: cluster}},
        default_cluster="acme-main",
        tags=TagSettings(),
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={"enabled": False, "rules": []},
    )


def test_render_lifecycle_disable_is_monotonic_and_reason_can_be_refined(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path / "__global/source/prod.json",
        {
            "connectctl": {
                "lifecycle": {
                    "disabled": True,
                    "reason": "Domain frozen",
                    "ticket": "OPS-42",
                }
            }
        },
    )
    manifest_path = (
        tmp_path
        / "payments"
        / "source"
        / "file"
        / "connector_payments__orders"
        / "prod_source_payments__orders.json"
    )
    _write_json(
        manifest_path,
        {
            "name": "prod.payments.orders.source.file.0",
            "connectctl": {
                "lifecycle": {
                    "disabled": False,
                    "reason": "Temporary downstream freeze",
                    "until": "2026-05-01",
                }
            },
            "config": {
                "connector.class": "org.apache.kafka.connect.file.FileStreamSourceConnector",
                "tasks.max": "1",
                "file": "/tmp/orders.txt",
                "topic": "orders",
            },
        },
    )

    rr = build_renderer(_settings(tmp_path), fs=LocalFileSystem()).render(manifest_path)

    assert rr.manifest.lifecycle.disabled is True
    assert rr.manifest.lifecycle.reason == "Temporary downstream freeze"
    assert rr.manifest.lifecycle.ticket == "OPS-42"
    assert rr.manifest.lifecycle.until == "2026-05-01"
    assert rr.manifest.lifecycle.disabled_sources == ("__global/source/prod.json",)
    assert rr.connectctl["lifecycle"]["disabled"] is True
    assert rr.connectctl["lifecycle"]["reason"] == "Temporary downstream freeze"


def test_render_lifecycle_disabled_requires_reason(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "__global/source/prod.json",
        {"connectctl": {"lifecycle": {"disabled": True}}},
    )
    manifest_path = (
        tmp_path
        / "payments"
        / "source"
        / "file"
        / "connector_payments__orders"
        / "prod_source_payments__orders.json"
    )
    _write_json(
        manifest_path,
        {
            "name": "prod.payments.orders.source.file.0",
            "config": {
                "connector.class": "org.apache.kafka.connect.file.FileStreamSourceConnector",
                "tasks.max": "1",
                "file": "/tmp/orders.txt",
                "topic": "orders",
            },
        },
    )

    with pytest.raises(RenderError, match="connectctl.lifecycle.reason is required"):
        build_renderer(_settings(tmp_path), fs=LocalFileSystem()).render(manifest_path)
