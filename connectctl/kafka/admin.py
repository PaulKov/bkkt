from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..exceptions import KafkaMetricsError
from ..models import KafkaConfig
from .metrics import (
    KafkaMetricsClient,
    _require_kafka_python,
    common_kafka_client_kwargs,
)

try:
    from kafka import KafkaAdminClient, KafkaConsumer, TopicPartition
    from kafka.admin import ConfigResource, ConfigResourceType, NewPartitions, NewTopic
except Exception:  # pragma: no cover
    KafkaAdminClient = None
    KafkaConsumer = None
    TopicPartition = None
    ConfigResource = None
    ConfigResourceType = None
    NewPartitions = None
    NewTopic = None


@dataclass(frozen=True)
class KafkaTopicPartition:
    partition: int
    leader: int | None = None
    replicas: tuple[int, ...] = ()
    isr: tuple[int, ...] = ()
    beginning_offset: int | None = None
    end_offset: int | None = None

    @property
    def message_count(self) -> int | None:
        if self.beginning_offset is None or self.end_offset is None:
            return None
        return max(0, int(self.end_offset) - int(self.beginning_offset))

    def to_payload(self) -> dict[str, Any]:
        return {
            "partition": self.partition,
            "leader": self.leader,
            "replicas": list(self.replicas),
            "isr": list(self.isr),
            "beginning_offset": self.beginning_offset,
            "end_offset": self.end_offset,
            "message_count": self.message_count,
        }


@dataclass(frozen=True)
class KafkaTopicDescription:
    name: str
    internal: bool = False
    partitions: tuple[KafkaTopicPartition, ...] = ()
    error: str | None = None

    @property
    def partition_count(self) -> int:
        return len(self.partitions)

    @property
    def end_offset_sum(self) -> int | None:
        offsets = [p.end_offset for p in self.partitions]
        if any(value is None for value in offsets):
            return None
        return sum(int(value or 0) for value in offsets)

    @property
    def message_count_sum(self) -> int | None:
        counts = [p.message_count for p in self.partitions]
        if any(value is None for value in counts):
            return None
        return sum(int(value or 0) for value in counts)

    def to_payload(self, *, include_partitions: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "internal": self.internal,
            "partition_count": self.partition_count,
            "end_offset_sum": self.end_offset_sum,
            "message_count_sum": self.message_count_sum,
        }
        if self.error:
            payload["error"] = self.error
        if include_partitions:
            payload["partitions"] = [p.to_payload() for p in self.partitions]
        return payload


@dataclass(frozen=True)
class KafkaConsumerGroupSummary:
    group_id: str
    protocol_type: str | None = None
    state: str | None = None
    members: int | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "protocol_type": self.protocol_type,
            "state": self.state,
            "members": self.members,
        }


@dataclass(frozen=True)
class KafkaConsumerGroupTopicLag:
    topic: str
    partitions: int
    committed_sum: int | None = None
    end_offset_sum: int | None = None
    lag_sum: int | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "partitions": self.partitions,
            "committed_sum": self.committed_sum,
            "end_offset_sum": self.end_offset_sum,
            "lag_sum": self.lag_sum,
        }


@dataclass(frozen=True)
class KafkaConsumerGroupDescription:
    summary: KafkaConsumerGroupSummary
    topics: tuple[KafkaConsumerGroupTopicLag, ...] = ()
    error: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = self.summary.to_payload()
        payload["topics"] = [topic.to_payload() for topic in self.topics]
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass(frozen=True)
class KafkaBrokerDescription:
    broker_id: int
    host: str | None = None
    port: int | None = None
    rack: str | None = None
    configs: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "broker_id": self.broker_id,
            "host": self.host,
            "port": self.port,
            "rack": self.rack,
        }
        if self.configs:
            payload["configs"] = dict(sorted(self.configs.items()))
        return payload


@dataclass(frozen=True)
class KafkaClusterDescription:
    cluster_id: str | None = None
    controller_id: int | None = None
    brokers: tuple[KafkaBrokerDescription, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "controller_id": self.controller_id,
            "broker_count": len(self.brokers),
            "brokers": [broker.to_payload() for broker in self.brokers],
        }


class KafkaAdminReadClient:
    """Read-only Kafka Admin facade used by BKKT CLI and UI.

    The class wraps `kafka-python` and normalizes its version-dependent return
    objects into stable BKKT DTOs. Mutation methods intentionally live outside
    this v0.5 foundation.
    """

    def __init__(self, cfg: KafkaConfig, client_id: str = "bkkt-kafka-admin"):
        _require_kafka_python()
        self.cfg = cfg
        self.client_id = client_id
        self._metrics = KafkaMetricsClient(cfg=cfg, client_id=client_id)

    def _common_kwargs(self) -> dict[str, Any]:
        return common_kafka_client_kwargs(cfg=self.cfg, client_id=self.client_id)

    def _admin(self):
        return KafkaAdminClient(**self._common_kwargs())

    def _consumer(self):
        return KafkaConsumer(
            enable_auto_commit=False,
            group_id=None,
            **self._common_kwargs(),
        )

    def list_topics(
        self,
        *,
        include_internal: bool = False,
        prefix: str | None = None,
        regex: str | None = None,
        limit: int | None = None,
    ) -> list[str]:
        names = self._metrics.list_topics()
        if not include_internal:
            names = [name for name in names if not name.startswith("__")]
        if prefix:
            names = [name for name in names if name.startswith(prefix)]
        if regex:
            rx = re.compile(regex)
            names = [name for name in names if rx.search(name)]
        if limit and limit > 0:
            names = names[: int(limit)]
        return sorted(names)

    def describe_topic(
        self, name: str, *, include_offsets: bool = True
    ) -> KafkaTopicDescription:
        admin = self._admin()
        consumer = self._consumer() if include_offsets else None
        try:
            raw_descriptions = admin.describe_topics([name])
            raw = raw_descriptions[0] if raw_descriptions else {}
            partitions = _topic_partitions_from_raw(raw)
            if include_offsets:
                partitions = _with_offsets(consumer, name, partitions)
            return KafkaTopicDescription(
                name=name,
                internal=bool(
                    _get(raw, "is_internal", "internal", default=name.startswith("__"))
                ),
                partitions=tuple(partitions),
                error=_raw_error(raw),
            )
        finally:
            _safe_close(admin)
            if consumer is not None:
                _safe_close(consumer)

    def describe_topics(
        self,
        names: Sequence[str],
        *,
        include_offsets: bool = False,
    ) -> list[KafkaTopicDescription]:
        return [
            self.describe_topic(str(name), include_offsets=include_offsets)
            for name in names
        ]

    def describe_topic_configs(self, name: str) -> dict[str, Any]:
        if ConfigResource is None or ConfigResourceType is None:
            return {}
        admin = self._admin()
        try:
            resource = ConfigResource(ConfigResourceType.TOPIC, str(name))
            return _normalize_configs(admin.describe_configs([resource]))
        finally:
            _safe_close(admin)

    def list_consumer_groups(
        self,
        *,
        prefix: str | None = None,
        regex: str | None = None,
        limit: int | None = None,
    ) -> list[KafkaConsumerGroupSummary]:
        admin = self._admin()
        try:
            raw_groups = admin.list_consumer_groups() or []
        finally:
            _safe_close(admin)
        groups = [_consumer_group_summary_from_raw(raw) for raw in raw_groups]
        if prefix:
            groups = [group for group in groups if group.group_id.startswith(prefix)]
        if regex:
            rx = re.compile(regex)
            groups = [group for group in groups if rx.search(group.group_id)]
        groups = sorted(groups, key=lambda item: item.group_id)
        if limit and limit > 0:
            groups = groups[: int(limit)]
        return groups

    def describe_consumer_group(
        self,
        group_id: str,
        *,
        topics: Sequence[str] | None = None,
    ) -> KafkaConsumerGroupDescription:
        admin = self._admin()
        consumer = self._consumer()
        try:
            summary = _describe_group_summary(admin, group_id)
            offsets = admin.list_consumer_group_offsets(group_id) or {}
            topic_filter = {str(topic) for topic in topics or [] if str(topic)}
            topic_lags = _group_lag_from_offsets(
                consumer,
                group_id=group_id,
                offsets=offsets,
                topic_filter=topic_filter,
            )
            return KafkaConsumerGroupDescription(
                summary=summary, topics=tuple(topic_lags)
            )
        except Exception as exc:
            return KafkaConsumerGroupDescription(
                summary=KafkaConsumerGroupSummary(group_id=group_id),
                error=str(exc),
            )
        finally:
            _safe_close(admin)
            _safe_close(consumer)

    def describe_cluster(
        self, *, include_configs: bool = False
    ) -> KafkaClusterDescription:
        admin = self._admin()
        try:
            raw = admin.describe_cluster()
            brokers = [
                _broker_from_raw(item)
                for item in (_get(raw, "brokers", default=()) or ())
            ]
            if include_configs:
                brokers = [_broker_with_configs(admin, broker) for broker in brokers]
            return KafkaClusterDescription(
                cluster_id=_as_optional_str(_get(raw, "cluster_id", "clusterId")),
                controller_id=_as_optional_int(
                    _get(raw, "controller_id", "controllerId")
                ),
                brokers=tuple(sorted(brokers, key=lambda item: item.broker_id)),
            )
        finally:
            _safe_close(admin)


class KafkaAdminWriteClient(KafkaAdminReadClient):
    """Guarded Kafka Admin writer used by GitOps plan/apply services."""

    def create_topic(
        self,
        *,
        name: str,
        partitions: int,
        replication_factor: int,
        configs: Mapping[str, Any] | None = None,
    ) -> None:
        if NewTopic is None:
            raise KafkaMetricsError("kafka-python NewTopic support is unavailable")
        admin = self._admin()
        try:
            topic = NewTopic(
                name=str(name),
                num_partitions=int(partitions),
                replication_factor=int(replication_factor),
                topic_configs={str(k): str(v) for k, v in (configs or {}).items()},
            )
            admin.create_topics(new_topics=[topic], validate_only=False)
        finally:
            _safe_close(admin)

    def increase_partitions(self, *, name: str, partitions: int) -> None:
        if NewPartitions is None:
            raise KafkaMetricsError("kafka-python NewPartitions support is unavailable")
        admin = self._admin()
        try:
            admin.create_partitions({str(name): NewPartitions(int(partitions))})
        finally:
            _safe_close(admin)

    def alter_topic_configs(self, *, name: str, configs: Mapping[str, Any]) -> None:
        if ConfigResource is None or ConfigResourceType is None:
            raise KafkaMetricsError(
                "kafka-python ConfigResource support is unavailable"
            )
        admin = self._admin()
        try:
            resource = ConfigResource(ConfigResourceType.TOPIC, str(name))
            resource.configs = {str(k): str(v) for k, v in configs.items()}
            admin.alter_configs([resource])
        finally:
            _safe_close(admin)


def _get(raw: Any, *names: str, default: Any = None) -> Any:
    if isinstance(raw, Mapping):
        for name in names:
            if name in raw:
                return raw[name]
    for name in names:
        if hasattr(raw, name):
            return getattr(raw, name)
    return default


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _as_tuple_int(value: Any) -> tuple[int, ...]:
    if value is None:
        return ()
    out: list[int] = []
    for item in value if isinstance(value, (list, tuple, set)) else [value]:
        try:
            out.append(int(_get(item, "nodeId", "node_id", "id", default=item)))
        except Exception:
            continue
    return tuple(out)


def _topic_partitions_from_raw(raw: Any) -> list[KafkaTopicPartition]:
    partitions = _get(raw, "partitions", default=()) or ()
    out: list[KafkaTopicPartition] = []
    for item in partitions:
        partition = _as_optional_int(_get(item, "partition", "partition_id"))
        if partition is None:
            continue
        out.append(
            KafkaTopicPartition(
                partition=partition,
                leader=_as_optional_int(_get(item, "leader")),
                replicas=_as_tuple_int(_get(item, "replicas")),
                isr=_as_tuple_int(_get(item, "isr")),
            )
        )
    return sorted(out, key=lambda item: item.partition)


def _with_offsets(
    consumer: Any, topic: str, partitions: Sequence[KafkaTopicPartition]
) -> list[KafkaTopicPartition]:
    if not partitions:
        return list(partitions)
    tps = [TopicPartition(topic, item.partition) for item in partitions]
    beginnings = consumer.beginning_offsets(tps)
    ends = consumer.end_offsets(tps)
    by_partition = {item.partition: item for item in partitions}
    out: list[KafkaTopicPartition] = []
    for tp in tps:
        base = by_partition[int(tp.partition)]
        out.append(
            KafkaTopicPartition(
                partition=base.partition,
                leader=base.leader,
                replicas=base.replicas,
                isr=base.isr,
                beginning_offset=_as_optional_int(beginnings.get(tp)),
                end_offset=_as_optional_int(ends.get(tp)),
            )
        )
    return out


def _raw_error(raw: Any) -> str | None:
    error = _get(raw, "error", "error_code", "errorCode")
    if error in (None, 0, "0"):
        return None
    return str(error)


def _consumer_group_summary_from_raw(raw: Any) -> KafkaConsumerGroupSummary:
    if isinstance(raw, (list, tuple)):
        group_id = str(raw[0]) if raw else ""
        protocol_type = str(raw[1]) if len(raw) > 1 and raw[1] is not None else None
        return KafkaConsumerGroupSummary(group_id=group_id, protocol_type=protocol_type)
    return KafkaConsumerGroupSummary(
        group_id=str(_get(raw, "group", "group_id", "groupId", default="")),
        protocol_type=_as_optional_str(_get(raw, "protocol_type", "protocolType")),
        state=_as_optional_str(_get(raw, "state")),
        members=_as_optional_int(_get(raw, "members")),
    )


def _describe_group_summary(admin: Any, group_id: str) -> KafkaConsumerGroupSummary:
    try:
        raw_items = admin.describe_consumer_groups([group_id]) or []
        raw = raw_items[0] if raw_items else {}
        members = _get(raw, "members", default=()) or ()
        member_count = len(members) if hasattr(members, "__len__") else None
        return KafkaConsumerGroupSummary(
            group_id=group_id,
            protocol_type=_as_optional_str(_get(raw, "protocol_type", "protocolType")),
            state=_as_optional_str(_get(raw, "state")),
            members=member_count,
        )
    except Exception:
        return KafkaConsumerGroupSummary(group_id=group_id)


def _group_lag_from_offsets(
    consumer: Any,
    *,
    group_id: str,
    offsets: Mapping[Any, Any],
    topic_filter: set[str],
) -> list[KafkaConsumerGroupTopicLag]:
    topic_partitions: dict[str, list[Any]] = {}
    committed_by_tp: dict[Any, int] = {}
    for tp, metadata in offsets.items():
        topic = str(getattr(tp, "topic", ""))
        if not topic or (topic_filter and topic not in topic_filter):
            continue
        topic_partitions.setdefault(topic, []).append(tp)
        offset = _as_optional_int(_get(metadata, "offset", default=metadata))
        if offset is not None:
            committed_by_tp[tp] = offset

    out: list[KafkaConsumerGroupTopicLag] = []
    for topic, tps in sorted(topic_partitions.items()):
        try:
            ends = consumer.end_offsets(tps)
            committed_sum = sum(committed_by_tp.get(tp, 0) for tp in tps)
            end_sum = sum(int(ends.get(tp, 0) or 0) for tp in tps)
            out.append(
                KafkaConsumerGroupTopicLag(
                    topic=topic,
                    partitions=len(tps),
                    committed_sum=committed_sum,
                    end_offset_sum=end_sum,
                    lag_sum=max(0, end_sum - committed_sum),
                )
            )
        except Exception as exc:
            raise KafkaMetricsError(
                f"Failed to calculate lag for group={group_id!r} topic={topic!r}: {exc}"
            ) from exc
    return out


def _broker_from_raw(raw: Any) -> KafkaBrokerDescription:
    broker_id = _as_optional_int(_get(raw, "nodeId", "node_id", "id", "broker_id"))
    if broker_id is None:
        broker_id = -1
    return KafkaBrokerDescription(
        broker_id=broker_id,
        host=_as_optional_str(_get(raw, "host")),
        port=_as_optional_int(_get(raw, "port")),
        rack=_as_optional_str(_get(raw, "rack")),
    )


def _broker_with_configs(
    admin: Any, broker: KafkaBrokerDescription
) -> KafkaBrokerDescription:
    if ConfigResource is None or ConfigResourceType is None:
        return broker
    resource = ConfigResource(ConfigResourceType.BROKER, str(broker.broker_id))
    try:
        raw_configs = admin.describe_configs([resource])
    except Exception:
        return broker
    configs = _normalize_configs(raw_configs)
    return KafkaBrokerDescription(
        broker_id=broker.broker_id,
        host=broker.host,
        port=broker.port,
        rack=broker.rack,
        configs=configs,
    )


def _normalize_configs(raw_configs: Any) -> dict[str, Any]:
    if isinstance(raw_configs, Mapping):
        raw_configs = next(iter(raw_configs.values()), raw_configs)
    if isinstance(raw_configs, Sequence) and not isinstance(raw_configs, (str, bytes)):
        raw_configs = raw_configs[0] if raw_configs else {}
    entries = _get(
        raw_configs, "resources", "config_entries", "configs", default=raw_configs
    )
    if isinstance(entries, Mapping):
        return {str(key): _config_value(value) for key, value in entries.items()}
    out: dict[str, Any] = {}
    for item in entries or []:
        name = _get(item, "name", "config_name")
        if name is None:
            continue
        out[str(name)] = _config_value(item)
    return out


def _config_value(raw: Any) -> Any:
    if isinstance(raw, (str, int, float, bool)) or raw is None:
        return raw
    return _get(raw, "value", default=str(raw))


def _safe_close(obj: Any) -> None:
    try:
        obj.close()
    except Exception:
        pass


__all__ = [
    "KafkaAdminReadClient",
    "KafkaAdminWriteClient",
    "KafkaBrokerDescription",
    "KafkaClusterDescription",
    "KafkaConsumerGroupDescription",
    "KafkaConsumerGroupSummary",
    "KafkaConsumerGroupTopicLag",
    "KafkaTopicDescription",
    "KafkaTopicPartition",
]
