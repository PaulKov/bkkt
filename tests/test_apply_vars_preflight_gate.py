from __future__ import annotations

import json
import logging
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from connectctl.adapters.filesystem import LocalFileSystem
from connectctl.config_models import (
    ExportConfig,
    NamingConfig,
    SafetyConfig,
    SyncConfig,
)
from connectctl.exceptions import ConfigError, ValidationError
from connectctl.models import ConnectClusterConfig, Environment, RepoConfig
from connectctl.services.apply.deploy_options import ApplyOptions
from connectctl.services.apply_service import ApplyService
from connectctl.settings_models import Settings, TagSettings


class _DryRunConnectApi:
    def __getattr__(self, name: str):  # pragma: no cover
        raise AssertionError(f"dry-run apply must not call Connect API: {name}")


@dataclass
class _Ctx:
    repo_root: Path
    settings: Settings
    logger: logging.Logger
    fs: LocalFileSystem

    def env(self, env_str: str) -> Environment:
        return Environment.from_str(env_str)

    def connect_target(
        self, env: Environment, cluster_name: str | None, *, throttle=None, timeout=None
    ):
        group = self.settings.cluster_groups[
            cluster_name or self.settings.default_cluster
        ]
        return SimpleNamespace(
            env=env,
            cluster=group[env],
            client=_DryRunConnectApi(),
        )

    def print_cluster_banner(self, target) -> None:
        return None


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _settings(repo_root: Path) -> Settings:
    cluster_cfg = ConnectClusterConfig(
        env=Environment.prod,
        urls=("http://localhost:8083",),
        kafka=None,
        name="default",
    )
    return Settings(
        repo=RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=()),
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


def _manifest(repo_root: Path) -> Path:
    path = (
        repo_root
        / "demo/source/postgres/connector_demo__source/prod.demo.source.source.postgres.0.json"
    )
    _write_json(
        path,
        {
            "name": "prod.demo.source.source.postgres.0",
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "${secretManager:${db.secret}:host}",
                "database.user": "${secretManager:${db.secret}:username}",
                "database.password": "${secretManager:${db.secret}:password}",
                "topic.prefix": "prod.demo.source",
            },
        },
    )
    return path


def _write_provider(repo_root: Path) -> Path:
    path = repo_root / "bkkt/var_providers/platform.py"
    _write_text(
        path,
        """
from connectctl.plugins import VarProviderContext, bkkt_var_provider

@bkkt_var_provider(
    name="platform.db",
    provides=("db.secret",),
    capabilities=("aws_secrets_read",),
)
def provide_db(*, ctx: VarProviderContext) -> dict[str, object]:
    domain = ctx.variables.get("domain", "missing")
    return {"db.secret": f"dbz-{domain}-prod"}
""",
    )
    return path


def _write_contract(repo_root: Path) -> Path:
    path = repo_root / "bkkt/var_providers/contracts/platform.db.yaml"
    _write_text(
        path,
        """
version: 1
providers:
  platform.db:
    capabilities:
      - aws_secrets_read
    provides:
      db.secret:
        type: string
        pattern: "^dbz-demo-prod$"
        sensitive: true
""",
    )
    return path


def _write_secret_index(repo_root: Path, *, keys: list[str]) -> Path:
    path = repo_root / "bkkt/external_refs.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {"secretManager": {"dbz-demo-prod": {"keys": keys}}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _args(
    repo_root: Path,
    manifest: Path,
    contract: Path,
    secret_index: Path,
    *,
    vars_preflight: bool = True,
    vars_preflight_reason: str | None = None,
) -> Namespace:
    return Namespace(
        env="prod",
        cluster=None,
        changed=False,
        base=None,
        head=None,
        dry_run=True,
        paths=[str(manifest.relative_to(repo_root))],
        expand_templates=False,
        show_vars=False,
        vars=['{"domain":"demo"}'],
        vars_file=None,
        vars_profile=None,
        reuse_overrides=True,
        reuse_from=None,
        print_config=False,
        strict_naming=True,
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
        vars_preflight=vars_preflight,
        vars_preflight_reason=vars_preflight_reason,
        vars_preflight_provider_contract=[str(contract)],
        vars_preflight_secret_index=str(secret_index),
    )


def test_apply_vars_preflight_uses_loaded_deploy_context_runtime_vars(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    manifest = _manifest(tmp_path)
    _write_provider(tmp_path)
    contract = _write_contract(tmp_path)
    secret_index = _write_secret_index(tmp_path, keys=["host", "username", "password"])
    logger = logging.getLogger("test.apply.vars_preflight.ok")
    caplog.set_level(logging.INFO, logger=logger.name)
    ctx = _Ctx(
        repo_root=tmp_path,
        settings=_settings(tmp_path),
        logger=logger,
        fs=LocalFileSystem(),
    )

    rc = ApplyService(ctx=ctx, logger=logger).run(
        _args(tmp_path, manifest, contract, secret_index)
    )

    assert rc == 0
    assert "Vars preflight ok" in caplog.text
    assert "provider_contracts=1" in caplog.text
    assert "secret_refs=3" in caplog.text


def test_apply_vars_preflight_blocks_secret_ref_drift_before_any_mutation(
    tmp_path: Path,
) -> None:
    manifest = _manifest(tmp_path)
    _write_provider(tmp_path)
    contract = _write_contract(tmp_path)
    secret_index = _write_secret_index(tmp_path, keys=["host"])
    logger = logging.getLogger("test.apply.vars_preflight.fail")
    ctx = _Ctx(
        repo_root=tmp_path,
        settings=_settings(tmp_path),
        logger=logger,
        fs=LocalFileSystem(),
    )

    with pytest.raises(ValidationError, match="Vars preflight blocked"):
        ApplyService(ctx=ctx, logger=logger).run(
            _args(tmp_path, manifest, contract, secret_index)
        )


def test_apply_options_require_reason_for_vars_preflight_break_glass() -> None:
    with pytest.raises(ConfigError, match="vars-preflight-reason"):
        ApplyOptions.from_args(
            _args(
                Path("/repo"),
                Path(
                    "/repo/demo/source/postgres/connector_demo__source/prod.demo.source.source.postgres.0.json"
                ),
                Path("/repo/bkkt/var_providers/contracts/platform.db.yaml"),
                Path("/repo/bkkt/external_refs.yaml"),
                vars_preflight=False,
            ),
            env=Environment.prod,
        )


def test_apply_options_accept_vars_preflight_break_glass_with_reason() -> None:
    options = ApplyOptions.from_args(
        _args(
            Path("/repo"),
            Path(
                "/repo/demo/source/postgres/connector_demo__source/prod.demo.source.source.postgres.0.json"
            ),
            Path("/repo/bkkt/var_providers/contracts/platform.db.yaml"),
            Path("/repo/bkkt/external_refs.yaml"),
            vars_preflight=False,
            vars_preflight_reason="Emergency rollback to known-good config",
        ),
        env=Environment.prod,
    )

    assert options.vars_preflight is False
    assert options.vars_preflight_reason == "Emergency rollback to known-good config"
