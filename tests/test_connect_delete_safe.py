from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

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
from connectctl.services.connect_delete_safety import (
    DeleteSafetyInspector,
    infer_target_topics,
    kafka_config_from_connector_config,
)
from connectctl.kafka.metrics import TopicStats
from connectctl.models import KafkaConfig


class _FakeConnect:
    base_urls = ("http://connect.test:8083",)

    def __init__(
        self,
        *,
        config: dict[str, str] | None,
        offsets: dict,
        status: ConnectorStatus | None = None,
    ) -> None:
        self.config = dict(config) if config is not None else None
        self.offsets = dict(offsets)
        self.status = status or ConnectorStatus(
            name="prod.domain.ds.source.mariadb.init.0",
            connector_state="RUNNING",
            worker_id="worker-1:8083",
            task_states=("RUNNING",),
            raw={},
        )
        self.deleted: list[str] = []
        self.calls: list[tuple[str, str]] = []

    def list_connectors(self):
        self.calls.append(("list_connectors", ""))
        return [self.status.name]

    def get_config(self, name: str):
        self.calls.append(("get_config", name))
        if self.config is None:
            raise AssertionError("get_config should not be used for missing fixture")
        return dict(self.config)

    def get_config_optional(self, name: str):
        self.calls.append(("get_config_optional", name))
        if self.config is None:
            return None
        return dict(self.config)

    def get_status(self, name: str) -> ConnectorStatus:
        self.calls.append(("get_status", name))
        return self.status

    def get_offsets(self, name: str):
        self.calls.append(("get_offsets", name))
        return dict(self.offsets)

    def delete(self, name: str) -> None:
        self.calls.append(("delete", name))
        self.deleted.append(name)


@dataclass
class _DummyCtx:
    repo_root: Path
    client: _FakeConnect
    logger: logging.Logger
    settings: Settings = field(init=False)

    def __post_init__(self) -> None:
        repo_cfg = RepoConfig(root=self.repo_root, connectors_root=self.repo_root)
        clusters = {
            env: ConnectClusterConfig(
                env=env,
                urls=("http://connect.test:8083",),
                kafka=None,
                name="acme-main",
            )
            for env in Environment
        }
        self.settings = Settings(
            repo=repo_cfg,
            clusters=clusters,
            cluster_groups={"acme-main": clusters},
            default_cluster="acme-main",
            tags=TagSettings(),
            naming=NamingConfig(),
            sync=SyncConfig(),
            safety=SafetyConfig(),
            export=ExportConfig(),
            config_tests={"enabled": False, "rules": []},
        )

    def env(self, value: str) -> Environment:
        return Environment.from_str(value)

    def resolve_cluster(self, env: Environment, cluster_name: str | None):
        return self.settings.cluster_groups[cluster_name or "acme-main"][env]

    def connect_client(
        self, env: Environment, cluster_name: str | None, *, throttle=None
    ):
        return self.client


def _logger(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    log.handlers = []
    log.setLevel(logging.INFO)
    return log


def _ctx(tmp_path: Path, client: _FakeConnect) -> _DummyCtx:
    return _DummyCtx(repo_root=tmp_path, client=client, logger=_logger(tmp_path.name))


def _initial_only_config(**overrides: str) -> dict[str, str]:
    cfg = {
        "connector.class": "io.debezium.connector.mariadb.MariaDbConnector",
        "snapshot.mode": "initial_only",
        "topic.prefix": "prod.domain.ds.source.mariadb.init.0.changes",
        "table.include.list": "db.table",
        "transforms.replaceTopicName.regex": r"prod\.domain\.ds\.source\.mariadb\.init\.0\.changes\.([^.]+)\.(.*)",
        "transforms.replaceTopicName.replacement": "cdc.prod.domain.ds.$1.$2.0",
    }
    cfg.update(overrides)
    return cfg


def _offsets(snapshot_marker=None) -> dict:
    offset = {
        "ts_sec": 1778860000,
        "file": "mysql-bin.000123",
        "pos": 42,
    }
    if snapshot_marker is not None:
        offset["snapshot"] = snapshot_marker
    return {
        "offsets": [
            {
                "partition": {"server": "prod.domain.ds.source.mariadb.init.0.changes"},
                "offset": offset,
            }
        ]
    }


def _run_delete(tmp_path: Path, client: _FakeConnect, *extra_args: str) -> int:
    ctx = _ctx(tmp_path, client)
    parser = build_parser()
    args = parser.parse_args(
        [
            "connect",
            "delete",
            "--env",
            "prod",
            "--names",
            "prod.domain.ds.source.mariadb.init.0",
            "-y",
            *extra_args,
        ]
    )
    return args.func(args, ctx=ctx, logger=ctx.logger)


def test_connect_delete_safe_default_allows_completed_initial_only(
    tmp_path: Path,
) -> None:
    client = _FakeConnect(config=_initial_only_config(), offsets=_offsets())

    assert _run_delete(tmp_path, client) == 0

    assert client.deleted == ["prod.domain.ds.source.mariadb.init.0"]
    assert (
        "get_config_optional",
        "prod.domain.ds.source.mariadb.init.0",
    ) in client.calls
    assert ("get_offsets", "prod.domain.ds.source.mariadb.init.0") in client.calls


def test_connect_delete_safe_blocks_active_initial_snapshot(tmp_path: Path) -> None:
    client = _FakeConnect(
        config=_initial_only_config(),
        offsets=_offsets(snapshot_marker=True),
    )

    with pytest.raises(ConfigError, match="active snapshot"):
        _run_delete(tmp_path, client)

    assert client.deleted == []


def test_connect_delete_unsafe_skips_pre_delete_checks(tmp_path: Path) -> None:
    client = _FakeConnect(
        config=_initial_only_config(),
        offsets=_offsets(snapshot_marker=True),
    )

    assert _run_delete(tmp_path, client, "--unsafe") == 0

    assert client.deleted == ["prod.domain.ds.source.mariadb.init.0"]
    assert (
        "get_config_optional",
        "prod.domain.ds.source.mariadb.init.0",
    ) not in client.calls
    assert ("get_offsets", "prod.domain.ds.source.mariadb.init.0") not in client.calls


def test_connect_delete_safe_keeps_backwards_compatible_non_initial_delete(
    tmp_path: Path,
) -> None:
    client = _FakeConnect(
        config={
            "connector.class": "io.confluent.connect.jdbc.JdbcSinkConnector",
            "topics": "topic.a",
        },
        offsets={},
    )

    assert _run_delete(tmp_path, client) == 0

    assert client.deleted == ["prod.domain.ds.source.mariadb.init.0"]
    assert (
        "get_config_optional",
        "prod.domain.ds.source.mariadb.init.0",
    ) in client.calls
    assert ("get_offsets", "prod.domain.ds.source.mariadb.init.0") not in client.calls


def test_infer_target_topics_applies_debezium_regex_router() -> None:
    assert infer_target_topics(_initial_only_config()) == (
        "cdc.prod.domain.ds.db.table.0",
    )


def test_kafka_config_from_connector_config_maps_msk_iam_to_oauthbearer() -> None:
    cfg = kafka_config_from_connector_config(
        {
            "bootstrap.servers": "b-1.cluster.abc.c8.kafka.eu-central-1.amazonaws.com:9098",
            "security.protocol": "SASL_SSL",
            "sasl.mechanism": "AWS_MSK_IAM",
        }
    )

    assert cfg is not None
    assert cfg.bootstrap_servers == (
        "b-1.cluster.abc.c8.kafka.eu-central-1.amazonaws.com:9098",
    )
    assert cfg.security_protocol == "SASL_SSL"
    assert cfg.sasl_mechanism == "OAUTHBEARER"
    assert cfg.iam_region == "eu-central-1"


def test_connect_delete_safe_keeps_idempotent_delete_for_missing_connector(
    tmp_path: Path,
) -> None:
    client = _FakeConnect(config=None, offsets={})

    assert _run_delete(tmp_path, client) == 0

    assert client.deleted == ["prod.domain.ds.source.mariadb.init.0"]
    assert (
        "get_config_optional",
        "prod.domain.ds.source.mariadb.init.0",
    ) in client.calls
    assert ("get_offsets", "prod.domain.ds.source.mariadb.init.0") not in client.calls


def test_initial_only_topic_offset_check_is_bounded(monkeypatch) -> None:
    class _SlowKafkaMetrics:
        def __init__(self, cfg, client_id: str = "test") -> None:
            self.cfg = cfg
            self.client_id = client_id

        def topic_end_offsets_sum(self, topic: str) -> TopicStats:
            time.sleep(2)
            return TopicStats(topic=topic, partitions=1, end_offset_sum=1)

    import connectctl.services.connect_delete_safety as safety

    monkeypatch.setattr(safety, "_TOPIC_OFFSET_CHECK_TIMEOUT_SECONDS", 0.1)
    client = _FakeConnect(config=_initial_only_config(), offsets=_offsets())
    inspector = DeleteSafetyInspector(
        connect=client,
        kafka=KafkaConfig(bootstrap_servers=("kafka.test:9092",)),
        kafka_metrics_factory=_SlowKafkaMetrics,
    )

    started = time.monotonic()
    report = inspector.inspect("prod.domain.ds.source.mariadb.init.0")
    elapsed = time.monotonic() - started

    assert elapsed < 1
    topic_checks = [
        check for check in report.checks if check.name.startswith("topic_offsets:")
    ]
    assert topic_checks
    assert topic_checks[0].status == "warn"
    assert "timed out after 0.1s" in topic_checks[0].detail
