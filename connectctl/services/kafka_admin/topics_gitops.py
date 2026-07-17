from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from ...app.context import CliContext
from ...cli_helpers.terminal_table import (
    TableColumn,
    format_lines,
    render_terminal_table,
)
from ...exceptions import ConfigError
from ...kafka.admin import KafkaAdminWriteClient
from ...kafka.resources import KafkaTopicManifest, load_topic_manifests
from ...models import KafkaConfig
from ...output import (
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
)
from .service import KafkaAdminFactory, KafkaAdminService, _KafkaScope

KafkaAdminWriterFactory = Callable[[KafkaConfig], Any]


@dataclass(frozen=True)
class KafkaTopicChange:
    topic: str
    action: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "action": self.action,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class KafkaTopicPlan:
    desired: KafkaTopicManifest
    exists: bool
    changes: tuple[KafkaTopicChange, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def has_changes(self) -> bool:
        return bool(self.changes)

    def to_payload(self) -> dict[str, Any]:
        return {
            "desired": self.desired.to_payload(),
            "exists": self.exists,
            "has_changes": self.has_changes,
            "changes": [change.to_payload() for change in self.changes],
            "warnings": list(self.warnings),
        }


class KafkaTopicGitOpsService:
    """Declarative Kafka topic plan/apply service with guarded writes."""

    def __init__(
        self,
        *,
        ctx: CliContext,
        logger=None,
        reader_factory: KafkaAdminFactory | None = None,
        writer_factory: KafkaAdminWriterFactory | None = None,
    ) -> None:
        self._inventory = KafkaAdminService(
            ctx=ctx,
            logger=logger,
            client_factory=reader_factory,
        )
        self.writer_factory = writer_factory or KafkaAdminWriteClient

    def run_topics_plan(self, args: argparse.Namespace) -> int:
        scope = self._inventory._scope(args)
        plans = self._build_plans(scope, _load_from_args(args))
        return _write_plan(args, scope=scope, plans=plans, applied=False)

    def run_topics_apply(self, args: argparse.Namespace) -> int:
        scope = self._inventory._scope(args)
        plans = self._build_plans(scope, _load_from_args(args))
        dry_run = bool(getattr(args, "dry_run", False))
        yes = bool(getattr(args, "yes", False))
        if not dry_run and not yes:
            raise ConfigError("Refusing to mutate Kafka topics without --yes")
        if not dry_run:
            self._apply_plans(scope, plans)
        return _write_plan(args, scope=scope, plans=plans, applied=not dry_run)

    def _build_plans(
        self, scope: _KafkaScope, manifests: list[KafkaTopicManifest]
    ) -> list[KafkaTopicPlan]:
        client = self._inventory.client_factory(scope.kafka)
        existing = set(client.list_topics(include_internal=True, limit=0))
        return [
            _plan_topic(client, manifest, exists=manifest.name in existing)
            for manifest in manifests
        ]

    def _apply_plans(self, scope: _KafkaScope, plans: list[KafkaTopicPlan]) -> None:
        writer = self.writer_factory(scope.kafka)
        for plan in plans:
            desired = plan.desired
            for change in plan.changes:
                if change.action == "create_topic":
                    writer.create_topic(
                        name=desired.name,
                        partitions=desired.partitions,
                        replication_factor=desired.replication_factor,
                        configs=desired.configs,
                    )
                elif change.action == "increase_partitions":
                    writer.increase_partitions(
                        name=desired.name,
                        partitions=int(change.details["to"]),
                    )
                elif change.action == "alter_configs":
                    writer.alter_topic_configs(
                        name=desired.name,
                        configs=change.details["to"],
                    )


def _load_from_args(args: argparse.Namespace) -> list[KafkaTopicManifest]:
    files = [Path(str(item)) for item in getattr(args, "file", []) or []]
    if not files:
        raise ConfigError("At least one --file is required")
    manifests: list[KafkaTopicManifest] = []
    for path in files:
        manifests.extend(load_topic_manifests(path))
    names = [item.name for item in manifests]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ConfigError(f"Duplicate Kafka topic manifests: {', '.join(duplicates)}")
    return manifests


def _plan_topic(
    client: Any, desired: KafkaTopicManifest, *, exists: bool
) -> KafkaTopicPlan:
    changes: list[KafkaTopicChange] = []
    warnings: list[str] = []
    if not exists:
        changes.append(
            KafkaTopicChange(
                topic=desired.name,
                action="create_topic",
                details=desired.to_payload(),
            )
        )
        return KafkaTopicPlan(desired=desired, exists=False, changes=tuple(changes))

    current = client.describe_topic(desired.name, include_offsets=False)
    if current.partition_count < desired.partitions:
        changes.append(
            KafkaTopicChange(
                topic=desired.name,
                action="increase_partitions",
                details={"from": current.partition_count, "to": desired.partitions},
            )
        )
    elif current.partition_count > desired.partitions:
        warnings.append(
            f"Topic `{desired.name}` has {current.partition_count} partitions; "
            f"BKKT will not reduce it to {desired.partitions}."
        )

    current_configs = _read_topic_configs(client, desired.name)
    config_delta = {
        key: value
        for key, value in desired.configs.items()
        if str(current_configs.get(key)) != str(value)
    }
    if config_delta:
        changes.append(
            KafkaTopicChange(
                topic=desired.name,
                action="alter_configs",
                details={
                    "from": {key: current_configs.get(key) for key in config_delta},
                    "to": config_delta,
                },
            )
        )

    return KafkaTopicPlan(
        desired=desired,
        exists=True,
        changes=tuple(changes),
        warnings=tuple(warnings),
    )


def _read_topic_configs(client: Any, topic: str) -> Mapping[str, Any]:
    if not hasattr(client, "describe_topic_configs"):
        return {}
    return client.describe_topic_configs(topic) or {}


def _write_plan(
    args: argparse.Namespace,
    *,
    scope: _KafkaScope,
    plans: list[KafkaTopicPlan],
    applied: bool,
) -> int:
    payload = {
        **scope.payload(),
        "kind": "kafka_topics_apply" if applied else "kafka_topics_plan",
        "applied": applied,
        "topic_count": len(plans),
        "change_count": sum(len(plan.changes) for plan in plans),
        "plans": [plan.to_payload() for plan in plans],
    }
    fmt = resolve_output_format(args)
    if is_machine_output(fmt):
        write_payload(payload, fmt=fmt)
    else:
        write_text(_plan_text(scope, plans=plans, applied=applied))
    return 0


def _plan_text(
    scope: _KafkaScope, *, plans: list[KafkaTopicPlan], applied: bool
) -> str:
    title = "Kafka topic apply result" if applied else "Kafka topic plan"
    lines = [
        f"# {title}",
        "",
        f"- env: `{scope.env.value}`",
        f"- cluster_group: `{scope.cluster.name}`",
        f"- topics: `{len(plans)}`",
        f"- changes: `{sum(len(plan.changes) for plan in plans)}`",
        "",
    ]
    rows: list[dict[str, str]] = []
    for plan in plans:
        changes = format_lines(change.action for change in plan.changes)
        warnings = format_lines(plan.warnings)
        rows.append(
            {
                "topic": plan.desired.name,
                "exists": "yes" if plan.exists else "no",
                "changes": changes,
                "warnings": warnings,
            }
        )
    lines.append(
        render_terminal_table(
            (
                TableColumn("topic", "Topic", max_width=48),
                TableColumn("exists", "Exists", max_width=6),
                TableColumn("changes", "Changes", max_width=28),
                TableColumn("warnings", "Warnings", max_width=72),
            ),
            rows,
        )
    )
    return "\n".join(lines) + "\n"


__all__ = ["KafkaTopicChange", "KafkaTopicGitOpsService", "KafkaTopicPlan"]
