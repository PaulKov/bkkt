from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

from .kafka.metrics import KafkaMetricsClient
from .kafka.topics import infer_topics
from .models import ConnectorManifest, ConnectorType


@dataclass(frozen=True)
class SmokeIssue:
    severity: str  # "warn" | "error"
    check: str
    message: str
    hint: Optional[str] = None


def infer_consumer_group_id(manifest: ConnectorManifest) -> Optional[str]:
    """Best-effort inference of consumer group id for sink connectors.

    Kafka Connect sink connectors usually have a consumer group. Some teams set it
    explicitly via consumer.override.group.id.
    """

    cfg = manifest.config
    for k in (
        "consumer.override.group.id",
        "consumer.group.id",
        "group.id",
    ):
        v = cfg.get(k)
        if v:
            return str(v).strip() or None

    # Fallback guess (common in Kafka Connect): connect-<connector-name>
    try:
        if manifest.info.connector_type == ConnectorType.sink:
            return f"connect-{manifest.name}"
    except Exception:
        pass
    return None


def _match_topics_by_regex(
    all_topics: Sequence[str], pattern: str, *, limit: int = 50
) -> List[str]:
    try:
        rx = re.compile(pattern)
    except re.error:
        return []
    matches = [t for t in all_topics if rx.match(t)]
    return matches[:limit]


def run_smoke_checks(
    manifest: ConnectorManifest,
    *,
    kafka: Optional[KafkaMetricsClient],
    max_pattern_matches: int = 50,
) -> List[SmokeIssue]:
    """Best-effort post-deploy smoke checks.

    The goal is to surface "obviously broken" situations early, without being overly
    opinionated. By default, callers should treat findings as warnings.
    """

    if kafka is None:
        return []

    issues: List[SmokeIssue] = []
    ti = infer_topics(manifest)

    # Resolve topic patterns -> concrete topics (best effort)
    all_topics: Optional[List[str]] = None

    def _ensure_all_topics() -> List[str]:
        nonlocal all_topics
        if all_topics is None:
            all_topics = kafka.list_topics()
        return all_topics

    consumed: List[str] = []
    produced: List[str] = []

    if ti.consumed_topics:
        consumed.extend(ti.consumed_topics)
    if ti.consumed_pattern:
        consumed.extend(
            _match_topics_by_regex(
                _ensure_all_topics(),
                str(ti.consumed_pattern),
                limit=max_pattern_matches,
            )
        )

    if ti.produced_topics:
        produced.extend(ti.produced_topics)
    if ti.produced_pattern:
        produced.extend(
            _match_topics_by_regex(
                _ensure_all_topics(),
                str(ti.produced_pattern),
                limit=max_pattern_matches,
            )
        )

    # Topic existence / partitions check
    def _check_topic_exists(topic: str, *, kind: str) -> None:
        st = kafka.topic_end_offsets_sum(topic)
        if st.partitions <= 0:
            issues.append(
                SmokeIssue(
                    severity="warn",
                    check="TOPIC_MISSING",
                    message=f"{kind} topic '{topic}' is missing or has 0 partitions.",
                    hint="Verify topic creation settings and connector permissions.",
                )
            )

    for t in sorted(set(consumed)):
        _check_topic_exists(t, kind="consumed")
    for t in sorted(set(produced)):
        _check_topic_exists(t, kind="produced")

    # Lag check for sinks
    try:
        is_sink = manifest.info.connector_type == ConnectorType.sink
    except Exception:
        is_sink = False

    if is_sink and consumed:
        gid = infer_consumer_group_id(manifest)
        if not gid:
            issues.append(
                SmokeIssue(
                    severity="warn",
                    check="GROUP_ID_UNKNOWN",
                    message="Unable to infer consumer group id for lag check.",
                    hint="Set consumer.override.group.id (recommended) to make lag checks reliable.",
                )
            )
        else:
            lags = kafka.consumer_group_lag_sum(gid, topics=sorted(set(consumed)))
            for lg in lags:
                if lg.lag_sum is None:
                    issues.append(
                        SmokeIssue(
                            severity="warn",
                            check="LAG_UNKNOWN",
                            message=f"Lag for group '{gid}' topic '{lg.topic}' is unknown (no offsets).",
                            hint="This can happen right after deploy or if the group has never committed offsets.",
                        )
                    )
                else:
                    if int(lg.lag_sum) > 0:
                        issues.append(
                            SmokeIssue(
                                severity="warn",
                                check="LAG_NONZERO",
                                message=f"Lag for group '{gid}' topic '{lg.topic}' = {int(lg.lag_sum)} messages.",
                                hint="Non-zero lag might be normal; investigate if it grows continuously.",
                            )
                        )

    # Sources: if we can infer produced topics/pattern and found nothing, warn.
    if (manifest.info.connector_type == ConnectorType.source) and (
        ti.produced_topics or ti.produced_pattern
    ):
        if not produced:
            issues.append(
                SmokeIssue(
                    severity="warn",
                    check="NO_OUTPUT_TOPICS",
                    message="No produced topics were found matching inferred output pattern.",
                    hint="If this is expected (empty snapshot / filters), ignore; otherwise check connector logs.",
                )
            )

    return issues


def format_smoke_text(issues: Sequence[SmokeIssue]) -> str:
    if not issues:
        return "✅ Smoke checks: ok"

    lines = ["⚠️ Smoke checks (best-effort):"]
    for i in issues:
        prefix = "-"
        msg = i.message
        if i.hint:
            msg += f" (hint: {i.hint})"
        lines.append(f"{prefix} [{i.check}] {msg}")
    return "\n".join(lines)
