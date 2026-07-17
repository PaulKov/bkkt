from __future__ import annotations

import argparse
from typing import Any, Callable, Sequence

from ...app.context import CliContext
from ...exceptions import ConfigError
from ...kafka.admin import KafkaAdminReadClient
from ...logging_utils import get_logger
from ...models import ConnectClusterConfig, Environment, KafkaConfig
from ...output import (
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
)
from ..admin_endpoints.resolver import EffectiveAdminEndpointResolver

KafkaAdminFactory = Callable[[KafkaConfig], Any]


class KafkaAdminService:
    """Read-only Kafka platform inventory service.

    The service is intentionally side-effect free. Mutating Kafka resources will
    use a separate plan/apply service so UI and CLI can share the same safety
    model.
    """

    def __init__(
        self,
        *,
        ctx: CliContext,
        logger=None,
        client_factory: KafkaAdminFactory | None = None,
    ) -> None:
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)
        self.client_factory = client_factory or KafkaAdminReadClient

    def run_topics_list(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        client = self.client_factory(scope.kafka)
        names = client.list_topics(
            include_internal=bool(getattr(args, "include_internal", False)),
            prefix=getattr(args, "prefix", None),
            regex=getattr(args, "regexp", None),
            limit=int(getattr(args, "limit", 500) or 500),
        )
        include_offsets = bool(getattr(args, "with_offsets", False))
        topics = (
            client.describe_topics(names, include_offsets=include_offsets)
            if include_offsets
            else []
        )
        payload_topics = (
            [topic.to_payload(include_partitions=False) for topic in topics]
            if include_offsets
            else [{"name": name} for name in names]
        )
        return self._write(
            args,
            payload={
                **scope.payload(),
                "kind": "topics_list",
                "topic_count": len(payload_topics),
                "topics": payload_topics,
            },
            text=_topics_list_text(
                scope, payload_topics, include_offsets=include_offsets
            ),
        )

    def run_topics_describe(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        client = self.client_factory(scope.kafka)
        topic = str(getattr(args, "topic", "") or "").strip()
        if not topic:
            raise ConfigError("topic is required")
        desc = client.describe_topic(
            topic,
            include_offsets=not bool(getattr(args, "no_offsets", False)),
        )
        payload = {
            **scope.payload(),
            "kind": "topic_describe",
            "topic": desc.to_payload(include_partitions=True),
        }
        return self._write(
            args, payload=payload, text=_topic_describe_text(scope, desc)
        )

    def run_groups_list(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        client = self.client_factory(scope.kafka)
        groups = client.list_consumer_groups(
            prefix=getattr(args, "prefix", None),
            regex=getattr(args, "regexp", None),
            limit=int(getattr(args, "limit", 500) or 500),
        )
        payload_groups = [group.to_payload() for group in groups]
        return self._write(
            args,
            payload={
                **scope.payload(),
                "kind": "groups_list",
                "group_count": len(payload_groups),
                "groups": payload_groups,
            },
            text=_groups_list_text(scope, payload_groups),
        )

    def run_groups_describe(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        client = self.client_factory(scope.kafka)
        group_id = str(getattr(args, "group", "") or "").strip()
        if not group_id:
            raise ConfigError("group is required")
        topics = _csv(getattr(args, "topic", None))
        desc = client.describe_consumer_group(group_id, topics=topics)
        payload = {
            **scope.payload(),
            "kind": "group_describe",
            "group": desc.to_payload(),
        }
        return self._write(
            args, payload=payload, text=_group_describe_text(scope, desc)
        )

    def run_groups_lag(self, args: argparse.Namespace) -> int:
        return self.run_groups_describe(args)

    def run_brokers_describe(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        client = self.client_factory(scope.kafka)
        desc = client.describe_cluster(
            include_configs=bool(getattr(args, "configs", False))
        )
        payload = {
            **scope.payload(),
            "kind": "brokers_describe",
            "cluster": desc.to_payload(),
        }
        return self._write(args, payload=payload, text=_brokers_text(scope, desc))

    def run_brokers_health(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        client = self.client_factory(scope.kafka)
        desc = client.describe_cluster(include_configs=False)
        payload = {
            **scope.payload(),
            "kind": "brokers_health",
            "status": "ok" if desc.brokers else "warn",
            "cluster": desc.to_payload(),
        }
        return self._write(args, payload=payload, text=_brokers_text(scope, desc))

    def _scope(self, args: argparse.Namespace) -> "_KafkaScope":
        env = Environment.from_str(str(getattr(args, "env")).strip().lower())
        cluster = self.ctx.resolve_cluster(env, getattr(args, "cluster", None))
        endpoint = EffectiveAdminEndpointResolver(self.ctx).resolve_kafka(
            env=env,
            cluster=cluster,
            override_bootstrap=getattr(args, "bootstrap_server", None),
        )
        return _KafkaScope(
            env=env,
            cluster=cluster,
            kafka=endpoint.config,
            bootstrap_source=endpoint.source_label,
        )

    def _write(
        self, args: argparse.Namespace, *, payload: dict[str, Any], text: str
    ) -> int:
        fmt = resolve_output_format(args)
        if is_machine_output(fmt):
            write_payload(payload, fmt=fmt)
        else:
            write_text(text)
        return 0


class _KafkaScope:
    def __init__(
        self,
        *,
        env: Environment,
        cluster: ConnectClusterConfig,
        kafka: KafkaConfig,
        bootstrap_source: str = "cluster config",
    ):
        self.env = env
        self.cluster = cluster
        self.kafka = kafka
        self.bootstrap_source = bootstrap_source

    def payload(self) -> dict[str, Any]:
        return {
            "env": self.env.value,
            "cluster_group": self.cluster.name,
            "bootstrap_servers": list(self.kafka.bootstrap_servers),
            "bootstrap_source": self.bootstrap_source,
        }


def _topics_list_text(
    scope: _KafkaScope, topics: Sequence[dict[str, Any]], *, include_offsets: bool
) -> str:
    lines = [_heading(scope, "Kafka topics")]
    if include_offsets:
        lines.append("| Topic | Partitions | End offsets | Messages |")
        lines.append("|---|---:|---:|---:|")
        for topic in topics:
            lines.append(
                "| `{name}` | {partitions} | {end} | {messages} |".format(
                    name=topic.get("name"),
                    partitions=topic.get("partition_count", "-"),
                    end=topic.get("end_offset_sum", "-"),
                    messages=topic.get("message_count_sum", "-"),
                )
            )
    else:
        lines.append("| Topic |")
        lines.append("|---|")
        for topic in topics:
            lines.append(f"| `{topic.get('name')}` |")
    return "\n".join(lines) + "\n"


def _topic_describe_text(scope: _KafkaScope, desc: Any) -> str:
    lines = [_heading(scope, f"Kafka topic `{desc.name}`")]
    lines.append(
        f"- partitions: `{desc.partition_count}`\n"
        f"- end_offset_sum: `{desc.end_offset_sum}`\n"
        f"- message_count_sum: `{desc.message_count_sum}`\n"
    )
    lines.append("| Partition | Leader | Replicas | ISR | Begin | End | Messages |")
    lines.append("|---:|---:|---|---|---:|---:|---:|")
    for part in desc.partitions:
        lines.append(
            "| {p} | {leader} | {replicas} | {isr} | {begin} | {end} | {messages} |".format(
                p=part.partition,
                leader=_dash(part.leader),
                replicas=", ".join(str(x) for x in part.replicas) or "-",
                isr=", ".join(str(x) for x in part.isr) or "-",
                begin=_dash(part.beginning_offset),
                end=_dash(part.end_offset),
                messages=_dash(part.message_count),
            )
        )
    return "\n".join(lines) + "\n"


def _groups_list_text(scope: _KafkaScope, groups: Sequence[dict[str, Any]]) -> str:
    lines = [_heading(scope, "Kafka consumer groups")]
    lines.append("| Group | Protocol | State | Members |")
    lines.append("|---|---|---|---:|")
    for group in groups:
        lines.append(
            "| `{group}` | {protocol} | {state} | {members} |".format(
                group=group.get("group_id"),
                protocol=group.get("protocol_type") or "-",
                state=group.get("state") or "-",
                members=_dash(group.get("members")),
            )
        )
    return "\n".join(lines) + "\n"


def _group_describe_text(scope: _KafkaScope, desc: Any) -> str:
    payload = desc.to_payload()
    lines = [_heading(scope, f"Kafka consumer group `{payload.get('group_id')}`")]
    lines.append(
        f"- state: `{payload.get('state') or '-'}`\n"
        f"- members: `{_dash(payload.get('members'))}`\n"
    )
    lines.append("| Topic | Partitions | Committed | End | Lag |")
    lines.append("|---|---:|---:|---:|---:|")
    for topic in payload.get("topics", []) or []:
        lines.append(
            "| `{topic}` | {partitions} | {committed} | {end} | {lag} |".format(
                topic=topic.get("topic"),
                partitions=topic.get("partitions"),
                committed=_dash(topic.get("committed_sum")),
                end=_dash(topic.get("end_offset_sum")),
                lag=_dash(topic.get("lag_sum")),
            )
        )
    if payload.get("error"):
        lines.append(f"\nError: `{payload['error']}`")
    return "\n".join(lines) + "\n"


def _brokers_text(scope: _KafkaScope, desc: Any) -> str:
    payload = desc.to_payload()
    lines = [_heading(scope, "Kafka brokers")]
    lines.append(
        f"- cluster_id: `{payload.get('cluster_id') or '-'}`\n"
        f"- controller_id: `{_dash(payload.get('controller_id'))}`\n"
        f"- broker_count: `{payload.get('broker_count')}`\n"
    )
    lines.append("| Broker | Host | Port | Rack |")
    lines.append("|---:|---|---:|---|")
    for broker in payload.get("brokers", []) or []:
        lines.append(
            "| {broker} | `{host}` | {port} | {rack} |".format(
                broker=broker.get("broker_id"),
                host=broker.get("host") or "-",
                port=_dash(broker.get("port")),
                rack=broker.get("rack") or "-",
            )
        )
    return "\n".join(lines) + "\n"


def _heading(scope: _KafkaScope, title: str) -> str:
    return (
        f"# {title}\n\n"
        f"- env: `{scope.env.value}`\n"
        f"- cluster_group: `{scope.cluster.name}`\n"
        f"- bootstrap_servers: `{', '.join(scope.kafka.bootstrap_servers)}`\n"
    )


def _dash(value: Any) -> Any:
    return "-" if value is None else value


def _csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in str(value).split(",") if item.strip())
