from __future__ import annotations

import json
import logging
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from connectctl.cli_parser import build_parser
from connectctl.exceptions import ConfigError, ConnectApiError, ValidationError
from connectctl.models import ConnectClusterConfig, Environment, RepoConfig
from connectctl.services.validate_connect_service import ValidateConnectService
from connectctl.settings_models import (
    ExportConfig,
    Settings,
    TagSettings,
)
from connectctl.config_models import NamingConfig, SafetyConfig, SyncConfig


class _RecordingConnectApi:
    def __init__(
        self,
        *,
        cluster_name: str,
        calls: list[tuple[str, str]],
        behaviors: dict[str, str],
    ) -> None:
        self.cluster_name = cluster_name
        self.calls = calls
        self.behaviors = behaviors

    def validate_manifest(self, manifest, max_errors: int = 20) -> None:
        self.calls.append((self.cluster_name, manifest.name))
        behavior = self.behaviors.get(manifest.name)
        if behavior == "plugin":
            raise ValidationError(f"plugin validation failed for {manifest.name}")
        if behavior == "runtime":
            raise ConnectApiError(f"connection refused for {manifest.name}")


@dataclass
class _DummyCtx:
    repo_root: Path
    settings: Settings
    logger: logging.Logger
    calls: list[tuple[str, str]]
    behaviors: dict[str, str]

    def env(self, env_str: str) -> Environment:
        return Environment.from_str(env_str)

    @property
    def fs(self):
        return None

    def connect_target(
        self, env: Environment, cluster_name: str | None, *, throttle=None, timeout=None
    ):
        group_name = cluster_name or self.settings.default_cluster
        cluster = self.settings.cluster_groups[group_name][env]
        client = _RecordingConnectApi(
            cluster_name=group_name,
            calls=self.calls,
            behaviors=self.behaviors,
        )
        return SimpleNamespace(env=env, cluster=cluster, client=client)

    def print_cluster_banner(self, target) -> None:
        return None


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
        cluster_groups={
            "acme-main": main,
            "acme-external": external,
        },
        default_cluster="acme-main",
        tags=TagSettings(),
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={"enabled": False, "rules": []},
    )


def _make_ctx(
    repo_root: Path,
    *,
    behaviors: dict[str, str] | None = None,
    config_tests: dict | None = None,
) -> _DummyCtx:
    settings = _make_settings(repo_root)
    if config_tests is not None:
        settings = Settings(
            repo=settings.repo,
            clusters=settings.clusters,
            cluster_groups=settings.cluster_groups,
            default_cluster=settings.default_cluster,
            tags=settings.tags,
            naming=settings.naming,
            sync=settings.sync,
            safety=settings.safety,
            export=settings.export,
            config_tests=config_tests,
        )
    return _DummyCtx(
        repo_root=repo_root,
        settings=settings,
        logger=_logger(f"validate-connect-{repo_root.name}"),
        calls=[],
        behaviors=behaviors or {},
    )


def _write_manifest(
    repo_root: Path,
    *,
    env: str,
    dataset: str,
    cluster: str,
    topic: str | None = None,
    config_name: str | None = None,
) -> Path:
    path = (
        repo_root
        / "payments"
        / "source"
        / "file"
        / f"connector_payments__{dataset}"
        / f"{env}_source_payments__{dataset}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest_name = f"{env}.payments.{dataset}.source.file.0"
    payload = {
        "name": manifest_name,
        "connectctl": {"cluster": cluster},
        "config": {
            "connector.class": "org.apache.kafka.connect.file.FileStreamSourceConnector",
            "tasks.max": "1",
            "file": f"/tmp/{dataset}.txt",
            "topic": topic or f"{env}_{dataset}",
        },
    }
    if config_name is not None:
        payload["config"]["name"] = config_name
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _bulk_args(*, env: str, cluster: str | None = None) -> Namespace:
    return Namespace(
        env=env,
        cluster=cluster,
        suppress_tag_conflicts=False,
        explain_routing=False,
        changed=False,
        all=True,
        base=None,
        head=None,
        strict_naming=False,
        max_errors=20,
        paths=[],
        vars=None,
        vars_file=None,
    )


def _selected_args(
    *, env: str, paths: list[str], cluster: str | None = None
) -> Namespace:
    return Namespace(
        env=env,
        cluster=cluster,
        suppress_tag_conflicts=False,
        explain_routing=False,
        changed=False,
        all=False,
        base=None,
        head=None,
        strict_naming=False,
        max_errors=20,
        paths=paths,
        vars=None,
        vars_file=None,
    )


def _write_accepted_drift_yaml(
    manifest_path: Path,
    *,
    live_name: str,
    repo_name: str,
) -> None:
    export_dir = manifest_path.parent / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "connector_name_live": live_name,
        "connector_name_repo": repo_name,
        "status": "accepted_drift",
        "accepted_drift": [
            {
                "key": "connector.name",
                "live_value": live_name,
                "repo_render_value": repo_name,
                "reason": "legacy/non-deployable live name normalized to canonical repo name",
                "safe_for_redeploy": False,
            }
        ],
    }
    (export_dir / "drift.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


def test_validate_connect_parser_accepts_bulk_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["validate-connect", "--all", "--env", "all", "--cluster", "all"]
    )
    assert args.cmd == "validate-connect"
    assert args.all is True
    assert args.env == "all"
    assert args.cluster == "all"


@pytest.mark.parametrize(
    "args, expected",
    [
        (
            Namespace(
                env="prod",
                cluster=None,
                suppress_tag_conflicts=False,
                explain_routing=False,
                changed=True,
                all=True,
                base=None,
                head=None,
                strict_naming=False,
                max_errors=20,
                paths=[],
                vars=None,
                vars_file=None,
            ),
            "--all нельзя использовать вместе с --changed",
        ),
        (
            Namespace(
                env="prod",
                cluster=None,
                suppress_tag_conflicts=False,
                explain_routing=False,
                changed=False,
                all=True,
                base=None,
                head=None,
                strict_naming=False,
                max_errors=20,
                paths=["foo.json"],
                vars=None,
                vars_file=None,
            ),
            "--all нельзя использовать вместе с explicit paths",
        ),
        (
            Namespace(
                env="all",
                cluster=None,
                suppress_tag_conflicts=False,
                explain_routing=False,
                changed=False,
                all=False,
                base=None,
                head=None,
                strict_naming=False,
                max_errors=20,
                paths=[],
                vars=None,
                vars_file=None,
            ),
            "--env all поддерживается только вместе с --all",
        ),
        (
            Namespace(
                env="prod",
                cluster="all",
                suppress_tag_conflicts=False,
                explain_routing=False,
                changed=False,
                all=False,
                base=None,
                head=None,
                strict_naming=False,
                max_errors=20,
                paths=[],
                vars=None,
                vars_file=None,
            ),
            "--cluster all поддерживается только вместе с --all",
        ),
    ],
)
def test_validate_connect_bulk_rejects_invalid_argument_combinations(
    tmp_path: Path, args: Namespace, expected: str
) -> None:
    ctx = _make_ctx(tmp_path)
    svc = ValidateConnectService(ctx=ctx, logger=ctx.logger)
    with pytest.raises(ConfigError, match=expected):
        svc.run(args)


def test_validate_connect_all_filters_only_selected_env(tmp_path: Path) -> None:
    _write_manifest(
        repo_root=tmp_path, env="dev", dataset="devmain", cluster="acme-main"
    )
    _write_manifest(
        repo_root=tmp_path,
        env="stage",
        dataset="stageexternal",
        cluster="acme-external",
    )
    _write_manifest(
        repo_root=tmp_path,
        env="prod",
        dataset="prodmain",
        cluster="acme-main",
    )
    _write_manifest(
        repo_root=tmp_path,
        env="prod",
        dataset="prodexternal",
        cluster="acme-external",
    )

    ctx = _make_ctx(tmp_path)
    svc = ValidateConnectService(ctx=ctx, logger=ctx.logger)

    rc = svc.run(_bulk_args(env="prod", cluster="all"))

    assert rc == 0
    assert ctx.calls == [
        ("acme-external", "prod.payments.prodexternal.source.file.0"),
        ("acme-main", "prod.payments.prodmain.source.file.0"),
    ]


def test_validate_connect_all_filters_by_normal_routing_cluster(
    tmp_path: Path,
) -> None:
    _write_manifest(
        repo_root=tmp_path, env="dev", dataset="devmain", cluster="acme-main"
    )
    _write_manifest(
        repo_root=tmp_path,
        env="stage",
        dataset="stageexternal",
        cluster="acme-external",
    )
    _write_manifest(
        repo_root=tmp_path,
        env="prod",
        dataset="prodmain",
        cluster="acme-main",
    )

    ctx = _make_ctx(tmp_path)
    svc = ValidateConnectService(ctx=ctx, logger=ctx.logger)

    rc = svc.run(_bulk_args(env="all", cluster="acme-main"))

    assert rc == 0
    assert ctx.calls == [
        ("acme-main", "dev.payments.devmain.source.file.0"),
        ("acme-main", "prod.payments.prodmain.source.file.0"),
    ]


def test_validate_connect_all_continues_after_failures_and_logs_summary(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _write_manifest(repo_root=tmp_path, env="prod", dataset="ok", cluster="acme-main")
    _write_manifest(
        repo_root=tmp_path,
        env="prod",
        dataset="localfail",
        cluster="acme-main",
        config_name="prod.payments.other.source.file.0",
    )
    _write_manifest(
        repo_root=tmp_path,
        env="prod",
        dataset="pluginfail",
        cluster="acme-main",
    )
    _write_manifest(
        repo_root=tmp_path,
        env="prod",
        dataset="runtimefail",
        cluster="acme-main",
    )

    ctx = _make_ctx(
        tmp_path,
        behaviors={
            "prod.payments.pluginfail.source.file.0": "plugin",
            "prod.payments.runtimefail.source.file.0": "runtime",
        },
    )
    svc = ValidateConnectService(ctx=ctx, logger=ctx.logger)

    with caplog.at_level(logging.INFO, logger=ctx.logger.name):
        rc = svc.run(_bulk_args(env="prod", cluster="all"))

    assert rc == 1
    assert ctx.calls == [
        ("acme-main", "prod.payments.ok.source.file.0"),
        ("acme-main", "prod.payments.pluginfail.source.file.0"),
        ("acme-main", "prod.payments.runtimefail.source.file.0"),
    ]

    text = caplog.text
    assert (
        "Kafka Connect bulk validation summary: checked=4 passed=1 failed=3 accepted_local_exceptions=0"
        in text
    )
    assert "env=prod checked=4 passed=1 failed=3 accepted_local_exceptions=0" in text
    assert (
        "cluster=acme-main checked=4 passed=1 failed=3 accepted_local_exceptions=0"
        in text
    )
    assert "FAIL [local-manifest]" in text
    assert "FAIL [connect-plugin]" in text
    assert "FAIL [upstream-runtime]" in text


def test_validate_connect_all_accepts_documented_legacy_name_exception(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    manifest_path = _write_manifest(
        repo_root=tmp_path,
        env="prod",
        dataset="legacy",
        cluster="acme-main",
        config_name="legacy.prod.payments.source.file",
    )
    _write_accepted_drift_yaml(
        manifest_path,
        live_name="legacy.prod.payments.source.file",
        repo_name="prod.payments.legacy.source.file.0",
    )

    ctx = _make_ctx(tmp_path)
    svc = ValidateConnectService(ctx=ctx, logger=ctx.logger)

    with caplog.at_level(logging.INFO, logger=ctx.logger.name):
        rc = svc.run(_bulk_args(env="prod", cluster="all"))

    assert rc == 0
    assert ctx.calls == [
        ("acme-main", "prod.payments.legacy.source.file.0"),
    ]
    text = caplog.text
    assert "ACCEPTED [local-manifest]" in text
    assert (
        "Kafka Connect bulk validation summary: checked=1 passed=1 failed=0 accepted_local_exceptions=1"
        in text
    )


def test_validate_connect_all_skips_disabled_manifests(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    path = _write_manifest(
        repo_root=tmp_path,
        env="prod",
        dataset="disabled",
        cluster="acme-main",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["connectctl"]["lifecycle"] = {
        "disabled": True,
        "reason": "DB retired",
        "ticket": "OPS-99",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    ctx = _make_ctx(tmp_path)
    svc = ValidateConnectService(ctx=ctx, logger=ctx.logger)

    with caplog.at_level(logging.INFO, logger=ctx.logger.name):
        rc = svc.run(_bulk_args(env="prod", cluster="all"))

    assert rc == 0
    assert ctx.calls == []
    assert "disabled_skipped=1" in caplog.text


def test_validate_connect_selected_applies_cluster_scoped_config_tests(
    tmp_path: Path,
) -> None:
    manifest_path = _write_manifest(
        repo_root=tmp_path,
        env="prod",
        dataset="externalguard",
        cluster="acme-external",
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["config"]["bootstrap.servers"] = "bad:9092"
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    ctx = _make_ctx(
        tmp_path,
        config_tests={
            "enabled": True,
            "rules": [
                {
                    "id": "no-inline-bootstrap-on-external",
                    "applies_to": {"cluster_group": ["acme-external"]},
                    "check": "forbid_key_patterns",
                    "patterns": ["bootstrap.servers"],
                }
            ],
        },
    )
    svc = ValidateConnectService(ctx=ctx, logger=ctx.logger)

    with pytest.raises(ValidationError, match="no-inline-bootstrap-on-external"):
        svc.run(
            _selected_args(
                env="prod",
                paths=[str(manifest_path.relative_to(tmp_path))],
            )
        )

    assert ctx.calls == []
