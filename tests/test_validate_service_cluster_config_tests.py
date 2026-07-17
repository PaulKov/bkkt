from __future__ import annotations

import json
import logging
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from connectctl.adapters.filesystem import LocalFileSystem
from connectctl.config_models import NamingConfig, SafetyConfig, SyncConfig
from connectctl.exceptions import ValidationError
from connectctl.models import ConnectClusterConfig, Environment, RepoConfig
from connectctl.services.validate_service import ValidateService
from connectctl.settings_models import (
    ExportConfig,
    Settings,
    TagSettings,
)


def _logger(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    log.handlers = []
    log.setLevel(logging.INFO)
    return log


def _settings(repo_root: Path) -> Settings:
    repo_cfg = RepoConfig(
        root=repo_root,
        connectors_root=(repo_root / "connectors").resolve(),
        ignore_dirs=(),
    )
    main = {
        env: ConnectClusterConfig(
            env=env,
            urls=(f"http://{env.value}.main:8083",),
            kafka=None,
            name="acme-main",
        )
        for env in Environment
    }
    foreign = {
        env: ConnectClusterConfig(
            env=env,
            urls=(f"http://{env.value}.foreign:8083",),
            kafka=None,
            name="acme-external_foreign_kafka",
        )
        for env in Environment
    }
    return Settings(
        repo=repo_cfg,
        clusters={env: main[env] for env in Environment},
        cluster_groups={
            "acme-main": main,
            "acme-external_foreign_kafka": foreign,
        },
        default_cluster="acme-main",
        tags=TagSettings(),
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={
            "enabled": True,
            "rules": [
                {
                    "id": "foreign-kafka-requires-bootstrap",
                    "applies_to": {"cluster_group": ["acme-external_foreign_kafka"]},
                    "check": "require_key_patterns",
                    "patterns": ["iceberg.kafka.bootstrap.servers"],
                }
            ],
        },
    )


def test_validate_service_uses_cluster_context_for_config_tests(tmp_path: Path) -> None:
    repo_root = tmp_path
    manifest_path = (
        repo_root
        / "connectors"
        / "partnerst"
        / "sink"
        / "iceberg"
        / "connector_partnerst__kafka"
        / "prod.partnerst.kafka.sink.raw.iceberg.0.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "name": "prod.partnerst.kafka.sink.raw.iceberg.0",
                "connectctl": {"cluster": "acme-external_foreign_kafka"},
                "config": {
                    "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
                    "tasks.max": "1",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    ctx = SimpleNamespace(
        repo_root=repo_root,
        settings=_settings(repo_root),
        logger=_logger("validate-service-cluster-config-tests"),
        fs=LocalFileSystem(),
        config_path=repo_root / "connectctl.yaml",
    )
    svc = ValidateService(ctx=ctx)

    with pytest.raises(ValidationError, match="foreign-kafka-requires-bootstrap"):
        svc.run(
            Namespace(
                env=None,
                changed=False,
                base=None,
                head=None,
                paths=[str(manifest_path.relative_to(repo_root))],
                strict_naming=False,
                strict_schema=False,
                strict_schema_max=20,
                strict_connector_dir=False,
                connector_dir_lint_scope="all",
                connector_dir_lint_max=20,
                vars=None,
                vars_file=None,
            )
        )
