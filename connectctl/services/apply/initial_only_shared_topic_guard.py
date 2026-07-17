from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ...exceptions import ValidationError
from ...kafka.topics import TopicInference, infer_topics_from_config
from ...models import ConnectorManifest
from ...ports import ConnectApi


@dataclass(frozen=True)
class _TopicOwnerConflict:
    connector: str
    status: str
    topics: tuple[str, ...]


def enforce_initial_only_shared_topic_guard(
    *,
    connect: ConnectApi,
    manifest: ConnectorManifest,
    logger: logging.Logger | None = None,
) -> None:
    """Prevent unsafe Debezium initial snapshots into live CDC topics.

    Kafka offsets are not row versions. If an ``initial_only`` connector writes
    snapshot ``r`` records to a topic already owned by a normal CDC source, those
    snapshot records can receive higher Kafka offsets than fresher live ``u``/``c``
    records. Offset-ordered ODS upserts can then regress row state.

    The safe invariant for BKKT apply is therefore strict: an ``initial_only``
    source may not share produced Kafka topics with any non-initial source
    connector already present on the same Kafka Connect cluster. Use isolated
    bootstrap topics plus a deterministic merge when historical loading is
    required for an existing CDC stream.
    """

    cfg = manifest.config
    if not _is_initial_only(cfg):
        return

    desired = infer_topics_from_config(cfg)
    if not _has_produced_targets(desired):
        raise ValidationError(
            f"Refusing to apply {manifest.name} with snapshot.mode=initial_only: "
            "BKKT could not infer produced Kafka topics from the rendered config. "
            "Shared-topic safety cannot be verified."
        )

    try:
        connector_names = tuple(str(name) for name in connect.list_connectors())
    except Exception as exc:
        raise ValidationError(
            f"Refusing to apply {manifest.name} with snapshot.mode=initial_only: "
            f"could not list live connectors to verify shared-topic safety: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    conflicts: list[_TopicOwnerConflict] = []
    for connector_name in connector_names:
        live_cfg = _get_live_config(connect, connector_name)
        if live_cfg is None or _is_initial_only(live_cfg):
            continue

        current = infer_topics_from_config(dict(live_cfg))
        if not _has_produced_targets(current):
            continue

        overlap = _produced_topic_overlap(desired, current)
        if not overlap:
            continue

        conflicts.append(
            _TopicOwnerConflict(
                connector=connector_name,
                status=_status_summary(connect, connector_name),
                topics=tuple(overlap),
            )
        )

    if not conflicts:
        return

    if logger is not None:
        logger.warning(
            "initial_only shared-topic guard blocked %s: %s conflict(s)",
            manifest.name,
            len(conflicts),
        )

    raise ValidationError(
        f"Refusing to apply {manifest.name} with snapshot.mode=initial_only: "
        "target Kafka topic(s) are already produced by non-initial source "
        "connector(s) on this Connect cluster. Snapshot records can be appended "
        "after live CDC records and overwrite fresher row state when downstream "
        "upserts follow Kafka offset order. Conflicts: "
        f"{_format_conflicts(conflicts)}. "
        "Use isolated bootstrap topics and a deterministic merge ordered by "
        "Debezium source timestamp, or remove the non-initial source topic owner "
        "before applying an init connector."
    )


def _is_initial_only(cfg: Mapping[str, Any]) -> bool:
    return str(cfg.get("snapshot.mode") or "").strip().lower() == "initial_only"


def _has_produced_targets(topics: TopicInference) -> bool:
    return bool(topics.produced_topics or topics.produced_pattern)


def _get_live_config(
    connect: ConnectApi, connector_name: str
) -> Mapping[str, Any] | None:
    getter = getattr(connect, "get_config_optional_fast", None)
    if callable(getter):
        return getter(connector_name)
    return connect.get_config_optional(connector_name)


def _status_summary(connect: ConnectApi, connector_name: str) -> str:
    try:
        status = connect.get_status(connector_name)
    except Exception as exc:
        return f"status_unavailable={type(exc).__name__}: {exc}"

    tasks = ",".join(status.task_states) if status.task_states else "-"
    return f"connector={status.connector_state}, tasks={tasks}"


def _produced_topic_overlap(
    desired: TopicInference, current: TopicInference
) -> tuple[str, ...]:
    matches: list[str] = []
    desired_topics = tuple(desired.produced_topics or ())
    current_topics = tuple(current.produced_topics or ())

    if desired_topics and current_topics:
        current_set = set(current_topics)
        matches.extend(topic for topic in desired_topics if topic in current_set)

    if desired_topics and current.produced_pattern:
        matches.extend(
            topic
            for topic in desired_topics
            if _matches_pattern(current.produced_pattern, topic)
        )

    if current_topics and desired.produced_pattern:
        matches.extend(
            topic
            for topic in current_topics
            if _matches_pattern(desired.produced_pattern, topic)
        )

    if (
        not matches
        and desired.produced_pattern
        and current.produced_pattern
        and desired.produced_pattern == current.produced_pattern
    ):
        matches.append(desired.produced_pattern)

    return tuple(_dedupe(matches))


def _matches_pattern(pattern: str, topic: str) -> bool:
    try:
        return bool(re.match(pattern, topic))
    except re.error:
        return False


def _dedupe(items: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return tuple(out)


def _format_conflicts(conflicts: Sequence[_TopicOwnerConflict]) -> str:
    rendered: list[str] = []
    for conflict in conflicts[:5]:
        topics = ", ".join(conflict.topics[:10])
        if len(conflict.topics) > 10:
            topics += f", ... +{len(conflict.topics) - 10}"
        rendered.append(f"{conflict.connector} [{conflict.status}] -> {topics}")
    if len(conflicts) > 5:
        rendered.append(f"... +{len(conflicts) - 5} connector(s)")
    return "; ".join(rendered)
