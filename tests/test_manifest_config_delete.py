from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

from connectctl.adapters.filesystem import LocalFileSystem
from connectctl.commands.compare_cmd import cmd_compare
from connectctl.config_models import (
    ExportConfig,
    NamingConfig,
    SafetyConfig,
    SyncConfig,
)
from connectctl.models import ConnectClusterConfig, Environment, RepoConfig
from connectctl.repo import ConnectorRepo, LayerResolver
from connectctl.rendering import ConnectorRenderer
from connectctl.rendering.unset_config import assert_final_config_has_no_nulls
from connectctl.services.apply_service import ApplyService
from connectctl.services.diff.service import DiffService
from connectctl.services.drift.service import DriftService
from connectctl.settings_models import Settings, TagSettings


class _DummyConnectApi:
    def __init__(self, configs: Dict[str, Dict[str, Any]] | None = None) -> None:
        self._configs = dict(configs or {})

    def get_config_optional(self, name: str):
        return self._configs.get(name)

    def list_connectors(self):
        return list(self._configs.keys())

    def __getattr__(self, name: str):  # pragma: no cover
        raise AssertionError(f"Unexpected ConnectApi call in test: {name}")


@dataclass
class _DummyCtx:
    repo_root: Path
    settings: Settings
    logger: logging.Logger
    fs: LocalFileSystem
    clients: Dict[str, _DummyConnectApi]

    def env(self, env_str: str) -> Environment:
        return Environment.from_str(env_str)

    def connect_target(
        self, env: Environment, cluster_name: str | None, *, throttle=None, timeout=None
    ):
        group_name = cluster_name or self.settings.default_cluster
        cluster = self.settings.cluster_groups[group_name][env]
        client = self.clients.setdefault(group_name, _DummyConnectApi())
        return SimpleNamespace(env=env, cluster=cluster, client=client)

    def print_cluster_banner(self, target) -> None:
        return None


def _logger() -> logging.Logger:
    log = logging.getLogger("bkkt-manifest-delete-tests")
    if not any(isinstance(h, logging.NullHandler) for h in log.handlers):
        log.addHandler(logging.NullHandler())
    return log


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _build_fixture(
    tmp_path: Path, *, explicit_unset: bool = False
) -> tuple[_DummyCtx, str, str, Dict[str, str], Any]:
    repo_root = tmp_path
    fs = LocalFileSystem()

    _write_json(
        repo_root / "__global/source/postgres/all.json",
        {
            "slot.name": "orders_slot_prod_0",
            "publication.autocreate.mode": "filtered",
        },
    )

    manifest_rel = (
        "acme/source/postgres/connector_acme__orders/"
        "prod.acme.orders.source.postgres.init.1.json"
    )
    manifest_path = repo_root / manifest_rel
    connector_name = "prod.acme.orders.source.postgres.init.1"
    manifest_obj: Dict[str, Any] = {
        "name": connector_name,
        "config": {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "tasks.max": "1",
            "plugin.name": "pgoutput",
            "database.hostname": "db.example",
            "database.port": "5432",
            "database.user": "user",
            "database.password": "secret",
            "database.dbname": "orders",
            "topic.prefix": "prod.acme.orders.source.postgres.init.0.changes",
        },
    }
    if explicit_unset:
        manifest_obj["bkkt"] = {"unset_config_keys": ["slot.name"]}
    else:
        manifest_obj["config"]["slot.name"] = None
    _write_json(manifest_path, manifest_obj)

    repo_cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    repo = ConnectorRepo(repo_cfg, fs=fs)
    renderer = ConnectorRenderer(repo=repo, layers=LayerResolver(repo_cfg, fs=fs))
    rr = renderer.render(manifest_path)

    cluster_cfg = ConnectClusterConfig(
        env=Environment.prod,
        urls=("http://localhost:8083",),
        name="default",
    )
    settings = Settings(
        repo=repo_cfg,
        clusters={Environment.prod: cluster_cfg},
        cluster_groups={"default": {Environment.prod: cluster_cfg}},
        default_cluster="default",
        tags=TagSettings(),
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={"enabled": False, "rules": []},
    )
    clients = {"default": _DummyConnectApi({connector_name: dict(rr.manifest.config)})}
    ctx = _DummyCtx(
        repo_root=repo_root,
        settings=settings,
        logger=_logger(),
        fs=fs,
        clients=clients,
    )
    return ctx, manifest_rel, connector_name, dict(rr.manifest.config), rr


def test_renderer_supports_null_to_remove_inherited_config_key(
    tmp_path: Path,
) -> None:
    _ctx, _manifest_rel, _connector_name, _rendered, rr = _build_fixture(tmp_path)

    assert rr.manifest.config["connector.class"] == (
        "io.debezium.connector.postgresql.PostgresConnector"
    )
    assert rr.manifest.config["publication.autocreate.mode"] == "filtered"
    assert "slot.name" not in rr.manifest.config
    assert "slot.name" not in rr.config_sources
    assert "slot.name" not in rr.config_sources_chain


def test_renderer_supports_bkkt_unset_config_keys(
    tmp_path: Path,
) -> None:
    _ctx, _manifest_rel, _connector_name, _rendered, rr = _build_fixture(
        tmp_path,
        explicit_unset=True,
    )

    assert "slot.name" not in rr.manifest.config
    assert rr.unset_config_keys == ("slot.name",)
    assert "slot.name" not in rr.config_sources
    assert "slot.name" not in rr.config_sources_chain


def test_final_config_guard_rejects_json_null_and_string_null(
    tmp_path: Path,
) -> None:
    _ctx, _manifest_rel, connector_name, _rendered, rr = _build_fixture(tmp_path)

    assert_final_config_has_no_nulls(
        rr.manifest.config,
        connector_name=connector_name,
        command="unit-test",
    )

    for bad_value in (None, "null", " NULL "):
        bad_config = dict(rr.manifest.config)
        bad_config["bad.key"] = bad_value
        try:
            assert_final_config_has_no_nulls(
                bad_config,
                connector_name=connector_name,
                command="unit-test",
            )
        except Exception as exc:
            assert "bad.key" in str(exc)
        else:  # pragma: no cover
            raise AssertionError(f"expected final config guard to reject {bad_value!r}")


def test_apply_service_dry_run_supports_deleted_inherited_key(tmp_path: Path) -> None:
    ctx, manifest_rel, _connector_name, _rendered, _rr = _build_fixture(tmp_path)

    args = argparse.Namespace(
        env="prod",
        cluster=None,
        changed=False,
        base=None,
        head=None,
        dry_run=True,
        paths=[manifest_rel],
        expand_templates=False,
        show_vars=False,
        vars=None,
        vars_file=None,
        reuse_overrides=True,
        reuse_from=None,
        print_config=False,
        strict_naming=False,
        policies=False,
        skip_if_unchanged=True,
        force=False,
        drop_if_exists=False,
        drop_if_failed=False,
        connect_validate=True,
        rollback_on_fail=False,
        wait_seconds=None,
        timeout_seconds=1,
        poll_interval_seconds=1,
        smoke=False,
        smoke_strict=False,
        auto_catalog=False,
        from_rendered=None,
        artifact_strict=False,
        jobs=1,
        rate_limit_per_second=None,
        rate_burst=None,
        suppress_tag_conflicts=False,
        explain_routing=False,
    )

    rc = ApplyService(ctx=ctx, logger=ctx.logger).run(args)
    assert rc == 0


def test_compare_diff_and_drift_treat_deleted_key_as_absent(
    tmp_path: Path, capsys
) -> None:
    ctx, manifest_rel, connector_name, rendered, _rr = _build_fixture(tmp_path)

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
    rc = cmd_compare(args_compare, ctx=ctx, logger=ctx.logger)
    assert rc == 0
    compare_payload = json.loads(capsys.readouterr().out)
    assert compare_payload["diff"]["in_sync"] is True
    assert compare_payload["desired"] == compare_payload["actual"]
    assert set(compare_payload["desired"].keys()) == set(rendered.keys())
    assert compare_payload["desired"]["database.password"] == "***"
    assert "slot.name" not in compare_payload["desired"]

    args_diff = argparse.Namespace(
        env="prod",
        cluster=None,
        suppress_tag_conflicts=False,
        changed=False,
        base=None,
        head=None,
        fail_on_drift=False,
        max_lines=50,
        output="json",
        json=False,
        show_vars=False,
        strict_naming=False,
        policies=False,
        paths=[manifest_rel],
        vars=None,
        vars_file=None,
    )
    rc = DiffService(ctx=ctx, logger=ctx.logger).run(args_diff)
    assert rc == 0
    diff_payload = json.loads(capsys.readouterr().out)
    assert diff_payload["counts"] == {
        "manifests_checked": 1,
        "in_sync": 1,
        "drifted": 0,
        "missing": 0,
    }
    assert diff_payload["missing"] == []
    assert diff_payload["drift"] == []

    args_drift = argparse.Namespace(
        env="prod",
        cluster=None,
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
    rc = DriftService(ctx=ctx, logger=ctx.logger).run(args_drift)
    assert rc == 0
    drift_payload = json.loads(capsys.readouterr().out)
    assert drift_payload["counts"] == {
        "manifests_checked": 1,
        "ok": 1,
        "drift": 0,
        "missing": 0,
    }
    assert drift_payload["detailed"] == []
