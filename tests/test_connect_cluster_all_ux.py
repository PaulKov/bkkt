from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from connectctl.cli_parser import build_parser
from connectctl.config_models import NamingConfig, SafetyConfig, SyncConfig
from connectctl.exceptions import ConfigError
from connectctl.models import (
    ConnectClusterConfig,
    ConnectorStatus,
    Environment,
    RepoConfig,
)
from connectctl.settings_models import (
    ExportConfig,
    Settings,
    TagSettings,
)


class _FakeConnect:
    def __init__(self, *, name: str, config: dict[str, Any] | None = None) -> None:
        self.name = name
        self.config = dict(config or {"table.include.list": "old.table"})
        self.updates: list[tuple[str, dict[str, Any]]] = []
        self.paused: list[str] = []
        self.deleted: list[str] = []

    def list_connectors(self) -> list[str]:
        return ["prod.connector.a"]

    def get_status(self, name: str) -> ConnectorStatus:
        return ConnectorStatus(
            name=name,
            connector_state="RUNNING",
            worker_id=f"{self.name}-worker",
            task_states=("RUNNING",),
            raw={
                "connector": {"state": "RUNNING", "worker_id": f"{self.name}-worker"},
                "tasks": [
                    {
                        "id": 0,
                        "state": "RUNNING",
                        "worker_id": f"{self.name}-worker",
                    }
                ],
            },
        )

    def get_config_optional(self, name: str) -> dict[str, Any] | None:
        if name != "prod.connector.a":
            return None
        return dict(self.config)

    def update_connector(self, name: str, desired: dict[str, Any]) -> None:
        self.config = dict(desired)
        self.updates.append((name, dict(desired)))

    def pause(self, name: str) -> None:
        self.paused.append(name)

    def delete(self, name: str) -> None:
        self.deleted.append(name)


@dataclass
class _DummyCtx:
    repo_root: Path
    settings: Settings
    logger: logging.Logger
    clients: dict[tuple[str, str], _FakeConnect]
    connect_calls: list[tuple[str, str]] = field(default_factory=list)
    mutation_checks: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def fs(self):
        from connectctl.adapters.filesystem import LocalFileSystem

        return LocalFileSystem()

    def env(self, value: str) -> Environment:
        return Environment.from_str(value)

    def resolve_cluster(self, env: Environment, cluster_name: str | None):
        group = cluster_name or self.settings.default_cluster
        return self.settings.cluster_groups[group][env]

    def connect_client(
        self, env: Environment, cluster_name: str | None, *, throttle=None
    ):
        group = cluster_name or self.settings.default_cluster
        self.connect_calls.append((group, env.value))
        return self.clients[(group, env.value)]

    def connect_target(
        self, env: Environment, cluster_name: str | None, *, throttle=None, timeout=None
    ):
        group = cluster_name or self.settings.default_cluster
        cluster = self.settings.cluster_groups[group][env]
        self.connect_calls.append((group, env.value))
        return SimpleNamespace(
            env=env,
            cluster=cluster,
            client=self.clients[(group, env.value)],
        )

    def print_cluster_banner(self, target) -> None:
        return None

    def assert_rest_mutation_allowed(
        self, env: Environment, cluster_name: str | None, *, command: str, unsafe: bool
    ) -> None:
        self.mutation_checks.append(
            (cluster_name or self.settings.default_cluster, env.value, command)
        )


def _logger(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    log.handlers = []
    log.setLevel(logging.INFO)
    return log


def _make_settings(repo_root: Path) -> Settings:
    repo_cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    groups: dict[str, dict[Environment, ConnectClusterConfig]] = {}
    for group in ("acme-main", "acme-source"):
        groups[group] = {
            env: ConnectClusterConfig(
                env=env,
                urls=(f"http://{group}.{env.value}:8083",),
                kafka=None,
                name=group,
            )
            for env in Environment
        }
    return Settings(
        repo=repo_cfg,
        clusters={env: groups["acme-main"][env] for env in Environment},
        cluster_groups=groups,
        default_cluster="acme-main",
        tags=TagSettings(),
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={"enabled": False, "rules": []},
    )


def _make_ctx(tmp_path: Path) -> _DummyCtx:
    settings = _make_settings(tmp_path)
    clients = {
        ("acme-main", "prod"): _FakeConnect(name="main"),
        ("acme-source", "prod"): _FakeConnect(name="source"),
    }
    return _DummyCtx(
        repo_root=tmp_path,
        settings=settings,
        logger=_logger(tmp_path.name),
        clients=clients,
    )


def _make_ctx_from_settings(
    tmp_path: Path,
    settings: Settings,
    clients: dict[tuple[str, str], _FakeConnect],
) -> _DummyCtx:
    return _DummyCtx(
        repo_root=tmp_path,
        settings=settings,
        logger=_logger(tmp_path.name),
        clients=clients,
    )


def test_connect_status_cluster_all_outputs_cluster_metadata_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx = _make_ctx(tmp_path)
    args = build_parser().parse_args(
        [
            "connect",
            "status",
            "--env",
            "prod",
            "--cluster",
            "all",
            "--names",
            "prod.connector.a",
            "--status",
            "short",
            "--output",
            "json",
        ]
    )

    assert args.func(args, ctx=ctx, logger=ctx.logger) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["env"] == "prod"
    assert [target["cluster_group"] for target in payload["targets"]] == [
        "acme-main",
        "acme-source",
    ]
    assert payload["counts"]["targets"] == 2
    assert payload["counts"]["connectors"] == 2
    assert all(
        item["cluster_group"] in {"acme-main", "acme-source"}
        for target in payload["targets"]
        for item in target["connectors"]
    )


def test_connect_status_cluster_all_skips_disabled_cluster_scopes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg_path = tmp_path / "connectctl.yaml"
    cfg_path.write_text(
        """
clusters:
  acme-main:
    prod:
      connect:
        scheme: http
        port: 8083
        hosts: ["main-prod"]
  acme-source:
    prod:
      lifecycle:
        disabled: true
        reason: source prod temporarily disabled for maintenance
        ticket: DATAPLAT-2652
      connect:
        scheme: http
        port: 8083
        hosts: ["source-prod"]
default_cluster: acme-main
""",
        encoding="utf-8",
    )
    settings = Settings.load(cfg_path, repo_root=tmp_path)
    ctx = _make_ctx_from_settings(
        tmp_path,
        settings,
        clients={("acme-main", "prod"): _FakeConnect(name="main")},
    )
    args = build_parser().parse_args(
        [
            "connect",
            "status",
            "--env",
            "prod",
            "--cluster",
            "all",
            "--names",
            "prod.connector.a",
            "--status",
            "short",
            "--output",
            "json",
        ]
    )

    assert args.func(args, ctx=ctx, logger=ctx.logger) == 0

    payload = json.loads(capsys.readouterr().out)
    assert [target["cluster_group"] for target in payload["targets"]] == ["acme-main"]
    assert ctx.connect_calls == [("acme-main", "prod")]


def test_connect_cluster_all_errors_when_all_scopes_are_disabled(
    tmp_path: Path,
) -> None:
    cfg_path = tmp_path / "connectctl.yaml"
    cfg_path.write_text(
        """
clusters:
  acme-main:
    prod:
      lifecycle:
        disabled: true
        reason: source prod temporarily disabled for maintenance
        ticket: DATAPLAT-2652
      connect:
        scheme: http
        port: 8083
        hosts: ["main-prod"]
default_cluster: acme-main
""",
        encoding="utf-8",
    )
    settings = Settings.load(cfg_path, repo_root=tmp_path)
    ctx = _make_ctx_from_settings(tmp_path, settings, clients={})
    args = build_parser().parse_args(
        [
            "connect",
            "status",
            "--env",
            "prod",
            "--cluster",
            "all",
            "--names",
            "prod.connector.a",
            "--status",
            "short",
        ]
    )

    with pytest.raises(ConfigError, match="DATAPLAT-2652"):
        args.func(args, ctx=ctx, logger=ctx.logger)


def test_connect_patch_cluster_all_dry_run_preserves_comma_value(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(tmp_path)
    args = build_parser().parse_args(
        [
            "connect",
            "patch",
            "--env",
            "prod",
            "--cluster",
            "all",
            "--names",
            "prod.connector.a",
            "--dry-run",
            "--diff",
            "--set",
            "table.include.list=orders.a,orders.b,orders.c",
        ]
    )

    assert args.func(args, ctx=ctx, logger=ctx.logger) == 0
    assert ctx.clients[("acme-main", "prod")].updates == []
    assert ctx.clients[("acme-source", "prod")].updates == []


def test_connect_patch_cluster_all_mutation_requires_yes_or_dry_run(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(tmp_path)
    args = build_parser().parse_args(
        [
            "connect",
            "patch",
            "--env",
            "prod",
            "--cluster",
            "all",
            "--names",
            "prod.connector.a",
            "--set",
            "errors.max.retries=1440",
        ]
    )

    with pytest.raises(ConfigError, match="--cluster all"):
        args.func(args, ctx=ctx, logger=ctx.logger)

    assert ctx.clients[("acme-main", "prod")].updates == []
    assert ctx.clients[("acme-source", "prod")].updates == []


def test_connect_patch_cluster_all_yes_updates_all_selected_targets(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(tmp_path)
    args = build_parser().parse_args(
        [
            "connect",
            "patch",
            "--env",
            "prod",
            "--cluster",
            "all",
            "--names",
            "prod.connector.a",
            "--yes",
            "--set",
            "errors.max.retries=1440",
        ]
    )

    assert args.func(args, ctx=ctx, logger=ctx.logger) == 0
    assert ctx.clients[("acme-main", "prod")].updates == [
        (
            "prod.connector.a",
            {"table.include.list": "old.table", "errors.max.retries": "1440"},
        )
    ]
    assert ctx.clients[("acme-source", "prod")].updates == [
        (
            "prod.connector.a",
            {"table.include.list": "old.table", "errors.max.retries": "1440"},
        )
    ]


def test_connect_pause_cluster_all_requires_explicit_selector(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(tmp_path)
    args = build_parser().parse_args(
        [
            "connect",
            "pause",
            "--env",
            "prod",
            "--cluster",
            "all",
            "--dry-run",
        ]
    )

    with pytest.raises(ConfigError, match="селектор"):
        args.func(args, ctx=ctx, logger=ctx.logger)


def test_connect_pause_cluster_all_dry_run_is_allowed_with_selector(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(tmp_path)
    args = build_parser().parse_args(
        [
            "connect",
            "pause",
            "--env",
            "prod",
            "--cluster",
            "all",
            "--names",
            "prod.connector.a",
            "--dry-run",
        ]
    )

    assert args.func(args, ctx=ctx, logger=ctx.logger) == 0
    assert ctx.clients[("acme-main", "prod")].paused == []
    assert ctx.clients[("acme-source", "prod")].paused == []


def test_connect_delete_cluster_all_dry_run_is_allowed_with_selector(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(tmp_path)
    args = build_parser().parse_args(
        [
            "connect",
            "delete",
            "--env",
            "prod",
            "--cluster",
            "all",
            "--names",
            "prod.connector.a",
            "--dry-run",
            "--unsafe",
        ]
    )

    assert args.func(args, ctx=ctx, logger=ctx.logger) == 0
    assert ctx.clients[("acme-main", "prod")].deleted == []
    assert ctx.clients[("acme-source", "prod")].deleted == []
