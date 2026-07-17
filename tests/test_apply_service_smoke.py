from __future__ import annotations

import json
import logging
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from connectctl.adapters.filesystem import LocalFileSystem
from connectctl.exceptions import (
    ConnectApiError,
    LifecycleDisabledError,
    ValidationError,
)
from connectctl.models import ConnectClusterConfig, Environment, RepoConfig
from connectctl.services.apply_service import ApplyService
from connectctl.settings_models import (
    ExportConfig,
    Settings,
    TagSettings,
)
from connectctl.config_models import NamingConfig, SafetyConfig, SyncConfig


class _DummyConnectApi:
    """Минимальный стаб ConnectApi для smoke-теста ApplyService.

    В DRY-RUN режиме реальные вызовы к Connect не должны происходить.
    Если вдруг код начнёт вызывать методы — пусть тест упадёт.
    """

    def __getattr__(self, name: str):  # pragma: no cover
        raise AssertionError(
            f"ConnectApi method should not be called in dry-run smoke test: {name}"
        )


class _FailingApplyConnectApi:
    def get_config_optional(self, name: str):
        return None

    def validate_manifest(self, manifest) -> None:
        return None

    def upsert(self, manifest) -> None:
        raise ConnectApiError("forced apply failure")


class _ExistingLegacyProtobufConnectApi:
    def __init__(self) -> None:
        self.upsert_called = False

    def get_config_optional(self, name: str):
        return {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
            "value.converter.schemas.enable": "true",
            "value.converter.ignore.default.for.nullables": "false",
            "value.converter.optional.for.nullables": "false",
            "value.converter.wrapper.for.nullables": "false",
            "value.converter.replace.null.with.default": "true",
        }

    def validate_manifest(self, manifest) -> None:
        return None

    def upsert(self, manifest) -> None:
        self.upsert_called = True


@dataclass
class _DummyCtx:
    repo_root: Path
    settings: Settings
    logger: logging.Logger
    fs: LocalFileSystem

    def env(self, env_str: str) -> Environment:
        return Environment.from_str(env_str)

    def connect_target(
        self, env: Environment, cluster_name: str | None, *, throttle=None, timeout=None
    ):
        # ApplyService вызывает ctx.connect_target(env, <cluster_group_name>)
        # cluster_name в нашем тесте совпадает с ключом cluster_groups.
        group = self.settings.cluster_groups[
            cluster_name or self.settings.default_cluster
        ]
        cluster = group[env]
        return SimpleNamespace(env=env, cluster=cluster, client=_DummyConnectApi())

    def print_cluster_banner(self, target) -> None:
        # Для теста баннер не важен.
        return None


@dataclass
class _FailingCtx(_DummyCtx):
    client: object

    def connect_target(
        self, env: Environment, cluster_name: str | None, *, throttle=None, timeout=None
    ):
        group = self.settings.cluster_groups[
            cluster_name or self.settings.default_cluster
        ]
        cluster = group[env]
        return SimpleNamespace(env=env, cluster=cluster, client=self.client)


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_apply_service_runs_in_dry_run_without_typeerrors(tmp_path: Path) -> None:
    """Регрессионный тест на баги уровня 'не тот аргумент / позиционные vs именованные'.

    Исторически ловили ошибки вида:
      TypeError: ConfigTestRunner.from_settings() takes 1 positional argument but 3 were given

    Этот тест прогоняет ApplyService.run в DRY-RUN на локальном мини-репозитории.
    """

    repo_root = tmp_path
    fs = LocalFileSystem()

    # Минимальный env-manifest.
    manifest_path = (
        repo_root
        / "e2e/source/file/connector_e2e__filesource/dev_source_e2e__filesource.json"
    )
    _write_json(
        manifest_path,
        {
            "name": "dev.e2e.filesource.source.file.0",
            "config": {
                "connector.class": "org.apache.kafka.connect.file.FileStreamSourceConnector",
                "tasks.max": "1",
                "file": "/tmp/e2e/source.txt",
                "topic": "e2e_source",
            },
        },
    )

    repo_cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())

    cluster_cfg = ConnectClusterConfig(
        env=Environment.dev, urls=("http://localhost:8083",), kafka=None, name="default"
    )
    settings = Settings(
        repo=repo_cfg,
        clusters={Environment.dev: cluster_cfg},
        cluster_groups={"default": {Environment.dev: cluster_cfg}},
        default_cluster="default",
        tags=TagSettings(),
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={"enabled": False, "rules": []},
    )

    ctx = _DummyCtx(
        repo_root=repo_root, settings=settings, logger=logging.getLogger("test"), fs=fs
    )

    args = Namespace(
        env="dev",
        cluster=None,
        changed=False,
        base=None,
        head=None,
        dry_run=True,
        paths=[str(manifest_path.relative_to(repo_root))],
        expand_templates=False,
        show_vars=False,
        vars=None,
        vars_file=None,
        reuse_overrides=True,
        reuse_from=None,
        print_config=False,
        strict_naming=True,
        policies=True,
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
        # concurrency
        jobs=1,
        rate_limit_per_second=None,
        rate_burst=None,
        # routing
        suppress_tag_conflicts=False,
        explain_routing=False,
    )

    svc = ApplyService(ctx=ctx, logger=ctx.logger)
    rc = svc.run(args)
    assert rc == 0


def test_apply_service_blocks_explicit_disabled_manifest(tmp_path: Path) -> None:
    repo_root = tmp_path
    fs = LocalFileSystem()

    manifest_path = (
        repo_root
        / "e2e/source/file/connector_e2e__filesource/dev_source_e2e__filesource.json"
    )
    _write_json(
        manifest_path,
        {
            "name": "dev.e2e.filesource.source.file.0",
            "connectctl": {
                "lifecycle": {
                    "disabled": True,
                    "reason": "Source stream paused",
                    "ticket": "OPS-77",
                }
            },
            "config": {
                "connector.class": "org.apache.kafka.connect.file.FileStreamSourceConnector",
                "tasks.max": "1",
                "file": "/tmp/e2e/source.txt",
                "topic": "e2e_source",
            },
        },
    )

    repo_cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    cluster_cfg = ConnectClusterConfig(
        env=Environment.dev, urls=("http://localhost:8083",), kafka=None, name="default"
    )
    settings = Settings(
        repo=repo_cfg,
        clusters={Environment.dev: cluster_cfg},
        cluster_groups={"default": {Environment.dev: cluster_cfg}},
        default_cluster="default",
        tags=TagSettings(),
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={"enabled": False, "rules": []},
    )
    ctx = _DummyCtx(
        repo_root=repo_root, settings=settings, logger=logging.getLogger("test"), fs=fs
    )

    args = Namespace(
        env="dev",
        cluster=None,
        changed=False,
        base=None,
        head=None,
        dry_run=True,
        paths=[str(manifest_path.relative_to(repo_root))],
        expand_templates=False,
        show_vars=False,
        vars=None,
        vars_file=None,
        reuse_overrides=True,
        reuse_from=None,
        print_config=False,
        strict_naming=True,
        policies=True,
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

    with pytest.raises(LifecycleDisabledError, match="refusing to apply"):
        ApplyService(ctx=ctx, logger=ctx.logger).run(args)


def test_apply_service_rejects_env_file_from_another_env(tmp_path: Path) -> None:
    """Нельзя деплоить stage/prod манифесты в другом окружении."""

    repo_root = tmp_path
    fs = LocalFileSystem()

    manifest_path = (
        repo_root
        / "e2e/source/file/connector_e2e__filesource/stage_source_e2e__filesource.json"
    )
    _write_json(
        manifest_path,
        {
            "name": "stage.e2e.filesource.source.file.0",
            "config": {
                "connector.class": "org.apache.kafka.connect.file.FileStreamSourceConnector",
                "tasks.max": "1",
                "file": "/tmp/e2e/source.txt",
                "topic": "e2e_source",
            },
        },
    )

    repo_cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())

    cluster_cfg = ConnectClusterConfig(
        env=Environment.dev, urls=("http://localhost:8083",), kafka=None, name="default"
    )
    settings = Settings(
        repo=repo_cfg,
        clusters={Environment.dev: cluster_cfg},
        cluster_groups={"default": {Environment.dev: cluster_cfg}},
        default_cluster="default",
        tags=TagSettings(),
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={"enabled": False, "rules": []},
    )

    ctx = _DummyCtx(
        repo_root=repo_root, settings=settings, logger=logging.getLogger("test"), fs=fs
    )

    # Запускаем apply в dev, но путь — stage_*.json.
    args = Namespace(
        env="dev",
        cluster=None,
        changed=False,
        base=None,
        head=None,
        dry_run=True,
        paths=[str(manifest_path.relative_to(repo_root))],
        expand_templates=False,
        show_vars=False,
        vars=None,
        vars_file=None,
        reuse_overrides=True,
        reuse_from=None,
        print_config=False,
        strict_naming=True,
        policies=True,
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

    svc = ApplyService(ctx=ctx, logger=ctx.logger)
    with pytest.raises(ValidationError):
        svc.run(args)


def test_apply_service_runs_in_dry_run_for_clickhouse_sink(tmp_path: Path) -> None:
    repo_root = tmp_path
    fs = LocalFileSystem()

    _write_json(
        repo_root / "__global/sink/clickhouse/all.json",
        {
            "config": {
                "connector.class": "com.clickhouse.kafka.connect.ClickHouseSinkConnector"
            }
        },
    )
    _write_json(
        repo_root / "__global/sink/clickhouse/types/raw/all.json",
        {
            "config": {
                "tasks.max": "1",
                "key.converter": "org.apache.kafka.connect.storage.StringConverter",
                "value.converter": "org.apache.kafka.connect.json.JsonConverter",
                "value.converter.schemas.enable": "false",
            }
        },
    )
    _write_json(
        repo_root / "acme/sink/clickhouse/stage.json",
        {
            "vars": {"clickhouse": {"secret": "stage/acme/clickhouse"}},
            "config": {
                "hostname": "${secretManager:${clickhouse.secret}:host}",
                "port": "${secretManager:${clickhouse.secret}:port}",
                "database": "${secretManager:${clickhouse.secret}:dbname}",
                "username": "${secretManager:${clickhouse.secret}:username}",
                "password": "${secretManager:${clickhouse.secret}:password}",
            },
        },
    )
    _write_json(
        repo_root / "acme/sink/clickhouse/connector_acme__events/all.json",
        {
            "config": {
                "topics": "acme.events",
                "topic2TableMap": "acme.events=events_raw",
            }
        },
    )
    manifest_path = (
        repo_root
        / "acme/sink/clickhouse/connector_acme__events/stage.acme.events.sink.raw.clickhouse.0.json"
    )
    _write_json(manifest_path, {"name": "stage.acme.events.sink.raw.clickhouse.0"})

    repo_cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    cluster_cfg = ConnectClusterConfig(
        env=Environment.stage,
        urls=("http://localhost:8083",),
        kafka=None,
        name="default",
    )
    settings = Settings(
        repo=repo_cfg,
        clusters={Environment.stage: cluster_cfg},
        cluster_groups={"default": {Environment.stage: cluster_cfg}},
        default_cluster="default",
        tags=TagSettings(),
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={"enabled": False, "rules": []},
    )
    ctx = _DummyCtx(
        repo_root=repo_root, settings=settings, logger=logging.getLogger("test"), fs=fs
    )

    args = Namespace(
        env="stage",
        cluster=None,
        changed=False,
        base=None,
        head=None,
        dry_run=True,
        paths=[str(manifest_path.relative_to(repo_root))],
        expand_templates=False,
        show_vars=False,
        vars=None,
        vars_file=None,
        reuse_overrides=True,
        reuse_from=None,
        print_config=False,
        strict_naming=True,
        policies=True,
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

    svc = ApplyService(ctx=ctx, logger=ctx.logger)
    rc = svc.run(args)
    assert rc == 0


def test_apply_service_failure_writes_bundle_with_prepared_manifest(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    fs = LocalFileSystem()

    manifest_path = (
        repo_root
        / "e2e/source/file/connector_e2e__filesource/dev_source_e2e__filesource.json"
    )
    _write_json(
        manifest_path,
        {
            "name": "dev.e2e.filesource.source.file.0",
            "config": {
                "connector.class": "org.apache.kafka.connect.file.FileStreamSourceConnector",
                "tasks.max": "1",
                "file": "/tmp/e2e/source.txt",
                "topic": "e2e_source",
                "bootstrap.servers": "should-be-pruned",
            },
            "connectctl": {
                "cluster": "default",
            },
        },
    )

    repo_cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())

    cluster_cfg = ConnectClusterConfig(
        env=Environment.dev,
        urls=("http://localhost:8083",),
        kafka=None,
        render_prune_config_keys=("bootstrap.servers",),
        name="default",
    )
    settings = Settings(
        repo=repo_cfg,
        clusters={Environment.dev: cluster_cfg},
        cluster_groups={"default": {Environment.dev: cluster_cfg}},
        default_cluster="default",
        tags=TagSettings(),
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={"enabled": False, "rules": []},
    )

    ctx = _FailingCtx(
        repo_root=repo_root,
        settings=settings,
        logger=logging.getLogger("test"),
        fs=fs,
        client=_FailingApplyConnectApi(),
    )

    bundle_root = repo_root / "custom-bundles"
    args = Namespace(
        env="dev",
        cluster=None,
        changed=False,
        base=None,
        head=None,
        dry_run=False,
        paths=[str(manifest_path.relative_to(repo_root))],
        expand_templates=False,
        show_vars=False,
        vars=None,
        vars_file=None,
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
        failure_bundle_dir=str(bundle_root),
    )

    svc = ApplyService(ctx=ctx, logger=ctx.logger)

    with pytest.raises(ConnectApiError, match="forced apply failure") as excinfo:
        svc.run(args)

    bundles = sorted(bundle_root.iterdir())
    assert len(bundles) == 1
    bundle_dir = bundles[0]

    bundle = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
    prepared = json.loads(
        (bundle_dir / "prepared_manifest.json").read_text(encoding="utf-8")
    )
    routing = json.loads((bundle_dir / "routing.json").read_text(encoding="utf-8"))
    readme = (bundle_dir / "README.md").read_text(encoding="utf-8")

    assert bundle["stage"] == "deploy"
    assert bundle["manifest"]["path"] == str(manifest_path)
    assert bundle["manifest"]["cluster_group"] == "default"
    assert prepared["name"] == "dev.e2e.filesource.source.file.0"
    assert "bootstrap.servers" not in prepared["config"]
    assert routing["routing"]["cluster"]["group"] == "default"
    assert "Suggested Remediation:" in readme
    assert "bkkt apply --env dev --cluster default --dry-run" in readme
    assert hasattr(excinfo.value, "__bkkt_inline_remediation__")


def test_apply_service_blocks_legacy_protobuf_nullable_migration_before_upsert(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    fs = LocalFileSystem()

    manifest_path = (
        repo_root
        / "domain/source/postgres/connector_domain__x/prod.domain.x.source.postgres.0.json"
    )
    _write_json(
        manifest_path,
        {
            "name": "prod.domain.x.source.postgres.0",
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "localhost",
                "database.port": "5432",
                "database.user": "u",
                "database.password": "p",
                "database.dbname": "db",
                "topic.prefix": "prod.domain.x",
                "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
                "value.converter.schemas.enable": "true",
                "value.converter.ignore.default.for.nullables": "true",
                "value.converter.optional.for.nullables": "true",
                "value.converter.wrapper.for.nullables": "true",
                "value.converter.replace.null.with.default": "false",
            },
        },
    )

    repo_cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    cluster_cfg = ConnectClusterConfig(
        env=Environment.prod,
        urls=("http://localhost:8083",),
        kafka=None,
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
    client = _ExistingLegacyProtobufConnectApi()
    ctx = _FailingCtx(
        repo_root=repo_root,
        settings=settings,
        logger=logging.getLogger("test"),
        fs=fs,
        client=client,
    )

    args = Namespace(
        env="prod",
        cluster=None,
        changed=False,
        base=None,
        head=None,
        dry_run=False,
        paths=[str(manifest_path.relative_to(repo_root))],
        expand_templates=False,
        show_vars=False,
        vars=None,
        vars_file=None,
        reuse_overrides=True,
        reuse_from=None,
        print_config=False,
        strict_naming=True,
        policies=False,
        skip_if_unchanged=False,
        force=False,
        drop_if_exists=False,
        drop_if_failed=False,
        connect_validate=False,
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

    with pytest.raises(ValidationError, match="Schema Registry preflight blocked"):
        ApplyService(ctx=ctx, logger=ctx.logger).run(args)

    assert client.upsert_called is False
