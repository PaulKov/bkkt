from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

from connectctl.config_models import (
    ExportConfig,
    NamingConfig,
    SafetyConfig,
    SyncConfig,
)
from connectctl.models import ConnectClusterConfig, Environment, RepoConfig
from connectctl.services.drift.service import DriftService
from connectctl.settings_models import Settings, TagSettings


class _FakeFs:
    def write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        path.write_text(content, encoding=encoding)


class _FakeCtx:
    def __init__(
        self, repo_root: Path, settings: Settings, logger: logging.Logger
    ) -> None:
        self.repo_root = repo_root
        self.settings = settings
        self.logger = logger
        self.fs = _FakeFs()

    def env(self, value: str) -> Environment:
        return Environment.from_str(value)

    def connect_target(
        self, env: Environment, cluster_name: str | None, *, timeout=None
    ):
        group = cluster_name or self.settings.default_cluster
        cluster = self.settings.cluster_groups[group][env]
        return SimpleNamespace(
            env=env,
            cluster=cluster,
            client=SimpleNamespace(),
        )

    def print_cluster_banner(self, target) -> None:
        return None


class _FakeRenderer:
    def render(self, path: Path, runtime_vars):
        return SimpleNamespace(
            manifest=SimpleNamespace(name=path.stem),
            connectctl={},
            connectctl_sources={},
        )


class _FakeRouter:
    def __init__(self, *args, **kwargs) -> None:
        return None

    def route_with_debug(self, *, connector_name, connectctl_meta, connectctl_sources):
        cluster = "acme-main" if connector_name.startswith("main") else "acme-external"
        return SimpleNamespace(cluster_name=cluster), {}


def _logger(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    log.handlers = []
    log.setLevel(logging.INFO)
    return log


def _make_settings(repo_root: Path) -> Settings:
    repo_cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    main = {
        env: ConnectClusterConfig(
            env=env,
            urls=(f"http://{env.value}.main:8083",),
            kafka=None,
            name="acme-main",
        )
        for env in Environment
    }
    external = {
        env: ConnectClusterConfig(
            env=env,
            urls=(f"http://{env.value}.external:8083",),
            kafka=None,
            name="acme-external",
        )
        for env in Environment
    }
    return Settings(
        repo=repo_cfg,
        clusters={env: main[env] for env in Environment},
        cluster_groups={"acme-main": main, "acme-external": external},
        default_cluster="acme-main",
        tags=TagSettings(),
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={"enabled": False, "rules": []},
    )


def test_drift_service_multi_cluster_returns_aggregated_payload(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    ctx = _FakeCtx(
        tmp_path, _make_settings(tmp_path), _logger(f"drift-{tmp_path.name}")
    )
    svc = DriftService(ctx=ctx, logger=ctx.logger)

    paths = [tmp_path / "main.json", tmp_path / "external.json"]
    for path in paths:
        path.write_text("{}", encoding="utf-8")

    def _fake_collect_drift(**kwargs):
        cluster_group = kwargs["cluster_group"]
        detailed = [{"name": f"{cluster_group}.connector", "status": "ok"}]
        return SimpleNamespace(
            manifests_checked=1,
            ok_count=1,
            disabled_skipped=0,
            drift_count=0,
            missing_count=0,
            group_stats_dt={"ok": 1},
            group_stats_dts={},
            drift_key_counter={},
            drift_override_source_counter={},
            detailed=detailed,
        )

    monkeypatch.setattr(
        "connectctl.services.drift.service.ConfigTestRunner.from_settings",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        "connectctl.services.drift.service.ConnectorRepo",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        "connectctl.services.drift.service.build_renderer",
        lambda *args, **kwargs: _FakeRenderer(),
    )
    monkeypatch.setattr(
        "connectctl.services.drift.service.load_runtime_vars_with_sources",
        lambda *args, **kwargs: ({}, {}),
    )
    monkeypatch.setattr(
        "connectctl.services.drift.service.select_manifest_paths",
        lambda **kwargs: paths,
    )
    monkeypatch.setattr("connectctl.services.drift.service.ClusterRouter", _FakeRouter)
    monkeypatch.setattr(
        "connectctl.services.drift.service.collect_drift", _fake_collect_drift
    )
    monkeypatch.setattr(
        "connectctl.services.drift.service.build_drift_markdown",
        lambda **kwargs: f"## {kwargs['tool_name']}\n",
    )

    args = SimpleNamespace(
        env="prod",
        cluster=None,
        clusters="acme-main,acme-external",
        output="json",
        output_file=None,
        include_diffs=False,
        max_lines=80,
        top=15,
        strict_naming=True,
        policies=True,
        fail_on_drift=False,
        yes=True,
        vars=None,
        vars_file=None,
    )

    rc = svc.run(args)
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "drift"
    assert payload["env"] == "prod"
    assert [item["cluster"]["group"] for item in payload["clusters"]] == [
        "acme-main",
        "acme-external",
    ]
