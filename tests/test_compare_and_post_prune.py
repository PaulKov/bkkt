from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import yaml

from connectctl.adapters.filesystem import LocalFileSystem
from connectctl.commands.compare_cmd import cmd_compare
from connectctl.config_models import (
    ExportConfig,
    NamingConfig,
    SafetyConfig,
    SyncConfig,
)
from connectctl.models import ConnectClusterConfig, Environment, RepoConfig
from connectctl.services.diff.service import DiffService
from connectctl.services.drift.service import DriftService
from connectctl.settings_models import Settings, TagSettings


class _FakeConnectApi:
    def __init__(self, configs: Dict[str, Dict[str, Any]]) -> None:
        self._configs = configs

    def get_config_optional(self, name: str):
        return self._configs.get(name)


@dataclass
class _DummyCtx:
    repo_root: Path
    settings: Settings
    logger: logging.Logger
    fs: LocalFileSystem
    clients: Dict[str, _FakeConnectApi]

    def env(self, env_str: str) -> Environment:
        return Environment.from_str(env_str)

    def connect_target(
        self, env: Environment, cluster_name: str | None, *, throttle=None, timeout=None
    ):
        group_name = cluster_name or self.settings.default_cluster
        cluster = self.settings.cluster_groups[group_name][env]
        return SimpleNamespace(
            env=env, cluster=cluster, client=self.clients[cluster.name]
        )

    def print_cluster_banner(self, target) -> None:
        return None


def _logger() -> logging.Logger:
    log = logging.getLogger("bkkt-compare-tests")
    if not any(isinstance(h, logging.NullHandler) for h in log.handlers):
        log.addHandler(logging.NullHandler())
    return log


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _build_ctx(tmp_path: Path) -> tuple[_DummyCtx, str, str]:
    repo_root = tmp_path
    fs = LocalFileSystem()

    manifest_rel = (
        "payments/sink/iceberg/connector_payments__orders/"
        "prod.payments.orders.sink.raw.iceberg.0.json"
    )
    manifest_path = repo_root / manifest_rel
    connector_dir = manifest_path.parent
    connector_name = "prod.payments.orders.sink.raw.iceberg.0"

    _write_json(connector_dir / "prod.json", {"tags": ["external"]})
    _write_json(
        manifest_path,
        {
            "name": connector_name,
            "config": {
                "connector.class": "org.example.IcebergSink",
                "tasks.max": "1",
                "bootstrap.servers": "broker:9092",
                "topic": "orders",
            },
        },
    )

    repo_cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    main_cluster = ConnectClusterConfig(
        env=Environment.prod,
        urls=("http://main:8083",),
        name="acme-main",
    )
    external_cluster = ConnectClusterConfig(
        env=Environment.prod,
        urls=("http://external:8083",),
        name="acme-external",
        render_prune_config_keys=("bootstrap.servers",),
    )
    settings = Settings(
        repo=repo_cfg,
        clusters={Environment.prod: main_cluster},
        cluster_groups={
            "acme-main": {Environment.prod: main_cluster},
            "acme-external": {Environment.prod: external_cluster},
        },
        default_cluster="acme-main",
        tags=TagSettings(
            definitions={"external": {"cluster": "acme-external"}},
            hard_conflict_params=("cluster",),
        ),
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={"enabled": False, "rules": []},
    )
    clients = {
        "acme-main": _FakeConnectApi({}),
        "acme-external": _FakeConnectApi(
            {
                connector_name: {
                    "connector.class": "org.example.IcebergSink",
                    "tasks.max": "1",
                    "topic": "orders",
                },
                "manual.connector": {
                    "connector.class": "org.example.IcebergSink",
                    "tasks.max": "7",
                    "topic": "orders",
                },
            }
        ),
    }

    ctx = _DummyCtx(
        repo_root=repo_root,
        settings=settings,
        logger=_logger(),
        fs=fs,
        clients=clients,
    )
    return ctx, manifest_rel, connector_name


def test_compare_live_uses_tag_routing_and_post_prune(tmp_path: Path, capsys) -> None:
    ctx, manifest_rel, connector_name = _build_ctx(tmp_path)

    args = argparse.Namespace(
        path=manifest_rel,
        against="live",
        name=None,
        file=None,
        output="json",
        json=False,
        show_vars=False,
        vars=None,
        vars_file=None,
        reuse_overrides=True,
        reuse_from=None,
        cluster=None,
        suppress_tag_conflicts=False,
        explain_routing=False,
        strict_naming=False,
        policies=False,
    )

    rc = cmd_compare(args, ctx=ctx, logger=ctx.logger)
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["routing"]["source"] == "tag"
    assert payload["routing"]["cluster"]["group"] == "acme-external"
    assert payload["source_b"]["type"] == "live"
    assert payload["source_b"]["connector_name"] == connector_name
    assert payload["pruned_config_keys"] == ["bootstrap.servers"]
    assert payload["diff"]["in_sync"] is True
    assert payload["desired"] == payload["actual"]
    assert "bootstrap.servers" not in payload["desired"]


def test_compare_supports_file_and_explicit_connector_sources(
    tmp_path: Path, capsys
) -> None:
    ctx, manifest_rel, _connector_name = _build_ctx(tmp_path)
    compare_file = tmp_path / "actual.yaml"
    compare_file.write_text(
        yaml.safe_dump(
            {
                "config": {
                    "connector.class": "org.example.IcebergSink",
                    "tasks.max": "2",
                    "topic": "orders",
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    args_file = argparse.Namespace(
        path=manifest_rel,
        against="file",
        name=None,
        file=str(compare_file),
        output="yaml",
        json=False,
        show_vars=False,
        vars=None,
        vars_file=None,
        reuse_overrides=True,
        reuse_from=None,
        cluster=None,
        suppress_tag_conflicts=False,
        explain_routing=False,
        strict_naming=False,
        policies=False,
    )

    rc = cmd_compare(args_file, ctx=ctx, logger=ctx.logger)
    assert rc == 0
    payload_yaml = yaml.safe_load(capsys.readouterr().out)
    assert payload_yaml["source_b"]["type"] == "file"
    assert payload_yaml["diff"]["changed_keys"] == ["tasks.max"]

    args_connector = argparse.Namespace(
        path=manifest_rel,
        against="connector",
        name="manual.connector",
        file=None,
        output="text",
        json=False,
        show_vars=False,
        vars=None,
        vars_file=None,
        reuse_overrides=True,
        reuse_from=None,
        cluster=None,
        suppress_tag_conflicts=False,
        explain_routing=False,
        strict_naming=False,
        policies=False,
    )

    rc = cmd_compare(args_connector, ctx=ctx, logger=ctx.logger)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Only in desired" in out
    assert "Changed (1)" in out
    assert "manual.connector" in out
    assert "bootstrap.servers" in out


def test_diff_uses_post_prune_comparison(tmp_path: Path, capsys) -> None:
    ctx, manifest_rel, _connector_name = _build_ctx(tmp_path)

    args = argparse.Namespace(
        env="prod",
        cluster=None,
        suppress_tag_conflicts=False,
        explain_routing=False,
        changed=False,
        base=None,
        head=None,
        fail_on_drift=False,
        max_lines=40,
        output="json",
        json=False,
        show_vars=False,
        strict_naming=False,
        policies=False,
        paths=[manifest_rel],
        vars=None,
        vars_file=None,
    )

    rc = DiffService(ctx=ctx, logger=ctx.logger).run(args)
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["comparison_mode"] == "post_prune"
    assert payload["counts"]["in_sync"] == 1
    assert payload["counts"]["drifted"] == 0


def test_drift_uses_post_prune_comparison(tmp_path: Path, capsys) -> None:
    ctx, manifest_rel, _connector_name = _build_ctx(tmp_path)

    args = argparse.Namespace(
        env="prod",
        cluster="acme-external",
        paths=[manifest_rel],
        changed=False,
        base=None,
        head=None,
        include_diffs=False,
        max_lines=80,
        top=15,
        output="json",
        json=False,
        output_file=None,
        fail_on_drift=False,
        strict_naming=False,
        policies=False,
    )

    rc = DriftService(ctx=ctx, logger=ctx.logger).run(args)
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["comparison_mode"] == "post_prune"
    assert payload["counts"]["ok"] == 1
    assert payload["counts"]["drift"] == 0


def test_compare_and_diff_skip_disabled_manifests(tmp_path: Path, capsys) -> None:
    ctx, manifest_rel, _connector_name = _build_ctx(tmp_path)
    manifest_path = tmp_path / manifest_rel
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["connectctl"] = {
        "tags": ["external"],
        "lifecycle": {
            "disabled": True,
            "reason": "External stream suspended",
            "ticket": "OPS-5",
        },
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    args_compare = argparse.Namespace(
        path=manifest_rel,
        against="live",
        name=None,
        file=None,
        output="json",
        json=False,
        show_vars=False,
        vars=None,
        vars_file=None,
        reuse_overrides=True,
        reuse_from=None,
        cluster=None,
        suppress_tag_conflicts=False,
        explain_routing=False,
        strict_naming=False,
        policies=False,
    )
    assert cmd_compare(args_compare, ctx=ctx, logger=ctx.logger) == 0
    compare_payload = json.loads(capsys.readouterr().out)
    assert compare_payload["status"] == "disabled"
    assert compare_payload["lifecycle"]["reason"] == "External stream suspended"

    args_diff = argparse.Namespace(
        env="prod",
        cluster=None,
        suppress_tag_conflicts=False,
        explain_routing=False,
        changed=False,
        base=None,
        head=None,
        fail_on_drift=False,
        max_lines=40,
        output="json",
        json=False,
        show_vars=False,
        strict_naming=False,
        policies=False,
        paths=[manifest_rel],
        vars=None,
        vars_file=None,
    )
    assert DiffService(ctx=ctx, logger=ctx.logger).run(args_diff) == 0
    diff_payload = json.loads(capsys.readouterr().out)
    assert diff_payload["lifecycle"]["disabled_skipped"] == 1
    assert diff_payload["counts"]["drifted"] == 0
