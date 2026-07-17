from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from connectctl.cli_parser import build_parser
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
from connectctl.config_models import NamingConfig, SafetyConfig, SyncConfig


class _FakeConnect:
    def __init__(
        self,
        *,
        names: list[str],
        statuses: dict[str, ConnectorStatus],
    ) -> None:
        self._names = list(names)
        self._statuses = dict(statuses)
        self.restarts: list[tuple[str, bool, bool]] = []

    def list_connectors(self):
        return list(self._names)

    def get_status(self, name: str) -> ConnectorStatus:
        return self._statuses[name]

    def restart(self, name: str, *, include_tasks: bool, only_failed: bool) -> None:
        self.restarts.append((name, include_tasks, only_failed))


@dataclass
class _DummyCtx:
    repo_root: Path
    settings: Settings
    logger: logging.Logger
    clients: dict[tuple[str, str], _FakeConnect]
    connect_calls: list[tuple[str, str]] = field(default_factory=list)

    def env(self, value: str) -> Environment:
        return Environment.from_str(value)

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


def _logger(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    log.handlers = []
    log.setLevel(logging.INFO)
    return log


def _make_settings(repo_root: Path) -> Settings:
    repo_cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    external = {
        env: ConnectClusterConfig(
            env=env,
            urls=(f"http://{env.value}.external:8083",),
            kafka=None,
            name="acme-external",
        )
        for env in Environment
    }
    external_alias = {
        env: ConnectClusterConfig(
            env=env,
            urls=(f"http://{env.value}.external:8083",),
            kafka=None,
            name="acme-external_alias",
        )
        for env in Environment
    }
    main = {
        env: ConnectClusterConfig(
            env=env,
            urls=(f"http://{env.value}.main:8083",),
            kafka=None,
            name="acme-main",
        )
        for env in Environment
    }
    return Settings(
        repo=repo_cfg,
        clusters={env: main[env] for env in Environment},
        cluster_groups={
            "acme-main": main,
            "acme-external": external,
            "acme-external_alias": external_alias,
        },
        default_cluster="acme-main",
        tags=TagSettings(),
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={"enabled": False, "rules": []},
    )


def _status(name: str, connector_state: str, *task_states: str) -> ConnectorStatus:
    return ConnectorStatus(
        name=name,
        connector_state=connector_state,
        worker_id="worker-1",
        task_states=tuple(task_states),
        raw={},
    )


def _make_ctx(tmp_path: Path) -> _DummyCtx:
    settings = _make_settings(tmp_path)
    client = _FakeConnect(
        names=["prod.connector.a", "prod.connector.b"],
        statuses={
            "prod.connector.a": _status("prod.connector.a", "RUNNING", "FAILED"),
            "prod.connector.b": _status("prod.connector.b", "RUNNING", "RUNNING"),
        },
    )
    clients = {
        ("acme-external", "prod"): client,
        ("acme-external_alias", "prod"): client,
        ("acme-main", "prod"): _FakeConnect(names=[], statuses={}),
    }
    return _DummyCtx(
        repo_root=tmp_path,
        settings=settings,
        logger=_logger(f"restart-{tmp_path.name}"),
        clients=clients,
    )


def test_connect_restart_bulk_dedupes_alias_clusters_and_uses_implicit_all_for_failed_tasks(
    tmp_path: Path, capsys
) -> None:
    ctx = _make_ctx(tmp_path)
    parser = build_parser()
    args = parser.parse_args(
        [
            "connect",
            "restart",
            "--env",
            "prod",
            "--clusters",
            "all",
            "--scope",
            "failed-tasks",
            "--dry-run",
            "--output",
            "json",
        ]
    )

    rc = args.func(args, ctx=ctx, logger=ctx.logger)
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["deduped_targets"] == 2
    assert payload["counts"]["selected"] == 2
    assert payload["counts"]["restart_candidates"] == 1
    assert payload["counts"]["restarted"] == 0
    assert payload["counts"]["skipped"] == 1
    assert len(ctx.connect_calls) == 2
    assert ("acme-external", "prod") in ctx.connect_calls
    assert ("acme-external_alias", "prod") not in ctx.connect_calls


def test_connect_restart_bulk_scope_all_requires_explicit_selector(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(tmp_path)
    parser = build_parser()
    args = parser.parse_args(
        [
            "connect",
            "restart",
            "--env",
            "prod",
            "--clusters",
            "all",
            "--scope",
            "all",
            "--dry-run",
            "--output",
            "json",
        ]
    )

    with pytest.raises(ConfigError):
        args.func(args, ctx=ctx, logger=ctx.logger)


def test_connect_restart_cluster_all_alias_uses_bulk_recovery(
    tmp_path: Path, capsys
) -> None:
    ctx = _make_ctx(tmp_path)
    parser = build_parser()
    args = parser.parse_args(
        [
            "connect",
            "restart",
            "--env",
            "prod",
            "--cluster",
            "all",
            "--scope",
            "failed-tasks",
            "--dry-run",
            "--output",
            "json",
        ]
    )

    rc = args.func(args, ctx=ctx, logger=ctx.logger)
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["deduped_targets"] == 2
    assert payload["counts"]["restart_candidates"] == 1
