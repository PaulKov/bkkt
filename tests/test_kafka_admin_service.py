from __future__ import annotations

from argparse import Namespace

from connectctl.cli_parser import build_parser
from connectctl.exceptions import ConfigError
from connectctl.kafka.admin import (
    KafkaBrokerDescription,
    KafkaClusterDescription,
    KafkaConsumerGroupDescription,
    KafkaConsumerGroupSummary,
    KafkaConsumerGroupTopicLag,
    KafkaTopicDescription,
    KafkaTopicPartition,
)
from connectctl.models import ConnectClusterConfig, Environment, KafkaConfig
from connectctl.services.kafka_admin import KafkaAdminService, KafkaTopicGitOpsService
from connectctl.kafka.resources import KafkaTopicManifest
from connectctl.services.kafka_admin.service import _KafkaScope
from connectctl.services.kafka_admin.topics_gitops import KafkaTopicPlan, _plan_text


class _DummyCtx:
    def __init__(self) -> None:
        self.logger = None
        self.cluster = ConnectClusterConfig(
            env=Environment.prod,
            urls=("http://connect:8083",),
            kafka=KafkaConfig(bootstrap_servers=("broker-1:9092",)),
            name="acme-main",
        )

    def resolve_cluster(self, env, cluster_name):
        assert env == Environment.prod
        assert cluster_name in (None, "acme-main")
        return self.cluster


class _FakeKafkaAdmin:
    def __init__(self, cfg: KafkaConfig):
        self.cfg = cfg

    def list_topics(self, **kwargs):
        assert self.cfg.bootstrap_servers == ("broker-1:9092",)
        names = ["orders", "orders.retry", "__consumer_offsets"]
        if not kwargs.get("include_internal"):
            names = [name for name in names if not name.startswith("__")]
        if kwargs.get("prefix"):
            names = [name for name in names if name.startswith(kwargs["prefix"])]
        return names[: kwargs.get("limit") or len(names)]

    def describe_topics(self, names, *, include_offsets=False):
        return [
            KafkaTopicDescription(
                name=name,
                partitions=(
                    KafkaTopicPartition(
                        partition=0,
                        leader=1,
                        replicas=(1, 2),
                        isr=(1, 2),
                        beginning_offset=10 if include_offsets else None,
                        end_offset=25 if include_offsets else None,
                    ),
                ),
            )
            for name in names
        ]

    def describe_topic(self, name, *, include_offsets=True):
        return self.describe_topics([name], include_offsets=include_offsets)[0]

    def describe_topic_configs(self, name):
        if name == "orders":
            return {"cleanup.policy": "delete", "retention.ms": "86400000"}
        return {}

    def list_consumer_groups(self, **kwargs):
        groups = [
            KafkaConsumerGroupSummary(
                group_id="connect-orders", protocol_type="consumer"
            ),
            KafkaConsumerGroupSummary(
                group_id="analytics-orders", protocol_type="consumer"
            ),
        ]
        if kwargs.get("prefix"):
            groups = [
                group for group in groups if group.group_id.startswith(kwargs["prefix"])
            ]
        return groups

    def describe_consumer_group(self, group_id, *, topics=()):
        topic = topics[0] if topics else "orders"
        return KafkaConsumerGroupDescription(
            summary=KafkaConsumerGroupSummary(
                group_id=group_id,
                protocol_type="consumer",
                state="Stable",
                members=2,
            ),
            topics=(
                KafkaConsumerGroupTopicLag(
                    topic=topic,
                    partitions=3,
                    committed_sum=90,
                    end_offset_sum=100,
                    lag_sum=10,
                ),
            ),
        )

    def describe_cluster(self, *, include_configs=False):
        return KafkaClusterDescription(
            cluster_id="cluster-a",
            controller_id=1,
            brokers=(
                KafkaBrokerDescription(
                    broker_id=1,
                    host="broker-1",
                    port=9092,
                    configs=(
                        {"log.retention.ms": "604800000"} if include_configs else {}
                    ),
                ),
            ),
        )


class _RecordingKafkaWriter:
    calls: list[tuple[str, dict]] = []

    def __init__(self, cfg: KafkaConfig):
        self.cfg = cfg

    @classmethod
    def reset(cls) -> None:
        cls.calls = []

    def create_topic(self, **kwargs):
        self.calls.append(("create_topic", kwargs))

    def increase_partitions(self, **kwargs):
        self.calls.append(("increase_partitions", kwargs))

    def alter_topic_configs(self, **kwargs):
        self.calls.append(("alter_topic_configs", kwargs))


def _args(**overrides):
    base = {
        "env": "prod",
        "cluster": "acme-main",
        "output": "json",
        "json": False,
    }
    base.update(overrides)
    return Namespace(**base)


def test_parser_exposes_kafka_readonly_namespace() -> None:
    parser = build_parser()
    assert (
        parser.parse_args(["kafka", "topics", "list", "--env", "prod"]).kafka_cmd
        == "topics"
    )
    assert (
        parser.parse_args(
            ["kafka", "groups", "lag", "--env", "prod", "connect-orders"]
        ).kafka_groups_cmd
        == "lag"
    )
    assert (
        parser.parse_args(
            ["kafka", "brokers", "health", "--env", "prod"]
        ).kafka_brokers_cmd
        == "health"
    )
    assert (
        parser.parse_args(
            ["kafka", "topics", "plan", "--env", "prod", "--file", "topics.yaml"]
        ).kafka_topics_cmd
        == "plan"
    )


def test_topics_list_outputs_stable_json(capsys) -> None:
    svc = KafkaAdminService(ctx=_DummyCtx(), client_factory=_FakeKafkaAdmin)
    rc = svc.run_topics_list(
        _args(
            prefix="orders",
            regexp=None,
            limit=10,
            include_internal=False,
            with_offsets=True,
        )
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert '"kind": "topics_list"' in out
    assert '"topic_count": 2' in out
    assert '"message_count_sum": 15' in out


def test_group_lag_outputs_topic_lag(capsys) -> None:
    svc = KafkaAdminService(ctx=_DummyCtx(), client_factory=_FakeKafkaAdmin)
    rc = svc.run_groups_lag(_args(group="connect-orders", topic="orders"))
    assert rc == 0
    out = capsys.readouterr().out
    assert '"kind": "group_describe"' in out
    assert '"lag_sum": 10' in out


def test_brokers_describe_can_include_configs(capsys) -> None:
    svc = KafkaAdminService(ctx=_DummyCtx(), client_factory=_FakeKafkaAdmin)
    rc = svc.run_brokers_describe(_args(configs=True))
    assert rc == 0
    out = capsys.readouterr().out
    assert '"kind": "brokers_describe"' in out
    assert '"broker_count": 1' in out
    assert '"log.retention.ms": "604800000"' in out


def test_topics_plan_detects_create_partition_and_config_changes(
    tmp_path, capsys
) -> None:
    manifest = tmp_path / "topics.yaml"
    manifest.write_text(
        """
topics:
  - name: orders
    partitions: 3
    replication_factor: 2
    configs:
      cleanup.policy: compact
      retention.ms: "86400000"
  - name: payments
    partitions: 6
    replication_factor: 3
    configs:
      cleanup.policy: delete
""",
        encoding="utf-8",
    )
    svc = KafkaTopicGitOpsService(ctx=_DummyCtx(), reader_factory=_FakeKafkaAdmin)

    rc = svc.run_topics_plan(_args(file=[str(manifest)], output="json"))

    assert rc == 0
    out = capsys.readouterr().out
    assert '"kind": "kafka_topics_plan"' in out
    assert '"action": "increase_partitions"' in out
    assert '"action": "alter_configs"' in out
    assert '"action": "create_topic"' in out


def test_topics_plan_text_uses_terminal_table_for_warnings() -> None:
    scope = _KafkaScope(
        env=Environment.prod,
        cluster=ConnectClusterConfig(
            env=Environment.prod,
            urls=("http://connect:8083",),
            kafka=KafkaConfig(bootstrap_servers=("broker-1:9092",)),
            name="acme-main",
        ),
        kafka=KafkaConfig(bootstrap_servers=("broker-1:9092",)),
    )
    text = _plan_text(
        scope,
        plans=[
            KafkaTopicPlan(
                desired=KafkaTopicManifest(
                    name="orders",
                    partitions=1,
                    replication_factor=2,
                ),
                exists=True,
                warnings=("first warning", "second warning"),
            )
        ],
        applied=False,
    )

    assert "<br>" not in text
    assert "first warning" in text
    assert "second warning" in text
    assert "┌" in text
    assert "|---|" not in text


def test_topics_apply_requires_yes_without_dry_run(tmp_path) -> None:
    manifest = tmp_path / "topics.yaml"
    manifest.write_text(
        "name: payments\npartitions: 3\nreplication_factor: 2\n",
        encoding="utf-8",
    )
    svc = KafkaTopicGitOpsService(ctx=_DummyCtx(), reader_factory=_FakeKafkaAdmin)

    try:
        svc.run_topics_apply(
            _args(file=[str(manifest)], dry_run=False, yes=False, output="json")
        )
    except ConfigError as exc:
        assert "without --yes" in str(exc)
    else:
        raise AssertionError("apply without --yes must fail")


def test_topics_apply_executes_recorded_changes_with_yes(tmp_path, capsys) -> None:
    _RecordingKafkaWriter.reset()
    manifest = tmp_path / "topics.yaml"
    manifest.write_text(
        """
name: payments
partitions: 6
replication_factor: 3
configs:
  cleanup.policy: delete
""",
        encoding="utf-8",
    )
    svc = KafkaTopicGitOpsService(
        ctx=_DummyCtx(),
        reader_factory=_FakeKafkaAdmin,
        writer_factory=_RecordingKafkaWriter,
    )

    rc = svc.run_topics_apply(
        _args(file=[str(manifest)], dry_run=False, yes=True, output="json")
    )

    assert rc == 0
    assert _RecordingKafkaWriter.calls == [
        (
            "create_topic",
            {
                "name": "payments",
                "partitions": 6,
                "replication_factor": 3,
                "configs": {"cleanup.policy": "delete"},
            },
        )
    ]
    assert '"applied": true' in capsys.readouterr().out
