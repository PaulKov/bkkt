from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import logging
import re
import signal
import threading
from typing import Any, Mapping, Sequence

from ..exceptions import ConfigError
from ..kafka.metrics import KafkaMetricsClient
from ..models import KafkaConfig
from ..ports import ConnectApi

_TOPIC_OFFSET_CHECK_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class DeleteSafetyCheck:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class DeleteSafetyReport:
    connector: str
    checks: tuple[DeleteSafetyCheck, ...] = ()

    @property
    def failed(self) -> bool:
        return any(check.status == "fail" for check in self.checks)

    def failure_message(self) -> str:
        failures = [check for check in self.checks if check.status == "fail"]
        details = "; ".join(f"{check.name}: {check.detail}" for check in failures)
        return f"Safe delete refused for {self.connector}: {details}"


@dataclass
class DeleteSafetyInspector:
    """Pre-delete guardrails for direct Kafka Connect connector deletion.

    The command-level UX has two modes:
    - safe (default): collect machine-checkable evidence before deleting;
    - unsafe: skip this inspector entirely and send DELETE directly.

    The specialized hard gate is intentionally focused on Debezium
    ``snapshot.mode=initial_only`` connectors because deleting them while a
    snapshot is still active is the common foot-gun. Other connector kinds keep
    backwards-compatible delete behavior and receive only a lightweight config
    read if safe mode is enabled.
    """

    connect: ConnectApi
    kafka: KafkaConfig | None = None
    kafka_metrics_factory: type[KafkaMetricsClient] = KafkaMetricsClient

    def inspect(self, name: str) -> DeleteSafetyReport:
        checks: list[DeleteSafetyCheck] = []
        try:
            cfg = self.connect.get_config_optional(name)
        except AttributeError:
            cfg = self.connect.get_config(name)
        except Exception as exc:
            return DeleteSafetyReport(
                connector=name,
                checks=(
                    DeleteSafetyCheck(
                        name="config",
                        status="fail",
                        detail=f"config unavailable: {type(exc).__name__}: {exc}",
                    ),
                ),
            )
        if cfg is None:
            return DeleteSafetyReport(
                connector=name,
                checks=(
                    DeleteSafetyCheck(
                        name="config",
                        status="skip",
                        detail="connector is already missing; Kafka Connect DELETE is idempotent",
                    ),
                ),
            )
        snapshot_mode = str(cfg.get("snapshot.mode") or "").strip()
        connector_class = str(cfg.get("connector.class") or "").strip()

        checks.append(
            DeleteSafetyCheck(
                name="config",
                status="pass",
                detail=(
                    f"connector.class={connector_class or '-'}, "
                    f"snapshot.mode={snapshot_mode or '-'}"
                ),
            )
        )

        if snapshot_mode != "initial_only":
            checks.append(
                DeleteSafetyCheck(
                    name="initial_only",
                    status="skip",
                    detail="connector is not snapshot.mode=initial_only; no specialized backfill gate applies",
                )
            )
            return DeleteSafetyReport(connector=name, checks=tuple(checks))

        checks.extend(self._inspect_initial_only(name=name, cfg=cfg))
        return DeleteSafetyReport(connector=name, checks=tuple(checks))

    def _inspect_initial_only(
        self, *, name: str, cfg: Mapping[str, Any]
    ) -> list[DeleteSafetyCheck]:
        checks: list[DeleteSafetyCheck] = []

        try:
            status = self.connect.get_status(name)
            checks.append(
                DeleteSafetyCheck(
                    name="status",
                    status="pass",
                    detail=(
                        f"connector={status.connector_state}, "
                        f"tasks={list(status.task_states) or '-'}"
                    ),
                )
            )
        except Exception as exc:
            checks.append(
                DeleteSafetyCheck(
                    name="status",
                    status="warn",
                    detail=f"status unavailable: {type(exc).__name__}: {exc}",
                )
            )

        try:
            offsets = self.connect.get_offsets(name)
            checks.extend(_offset_checks(offsets))
        except Exception as exc:
            checks.append(
                DeleteSafetyCheck(
                    name="offsets",
                    status="fail",
                    detail=f"offsets unavailable for initial_only connector: {type(exc).__name__}: {exc}",
                )
            )

        topics = infer_target_topics(cfg)
        if topics:
            checks.append(
                DeleteSafetyCheck(
                    name="target_topics",
                    status="pass",
                    detail=", ".join(topics),
                )
            )
            checks.extend(self._topic_offset_checks(topics=topics, cfg=cfg))
        else:
            checks.append(
                DeleteSafetyCheck(
                    name="target_topics",
                    status="warn",
                    detail="could not infer target topics from topic.prefix/table.include.list/RegexRouter",
                )
            )

        checks.append(
            DeleteSafetyCheck(
                name="source_count",
                status="warn",
                detail=(
                    "source DB count is environment-specific and remains a manual gate; "
                    "run the incident/runbook query when DB access is available"
                ),
            )
        )
        return checks

    def _topic_offset_checks(
        self, *, topics: Sequence[str], cfg: Mapping[str, Any]
    ) -> list[DeleteSafetyCheck]:
        kafka = self.kafka or kafka_config_from_connector_config(cfg)
        if kafka is None:
            return [
                DeleteSafetyCheck(
                    name="topic_offsets",
                    status="warn",
                    detail="Kafka config is unavailable; topic end offsets were not checked",
                )
            ]

        checks: list[DeleteSafetyCheck] = []
        try:
            with _suppress_kafka_client_logs():
                client = self.kafka_metrics_factory(kafka, client_id="bkkt-safe-delete")
                for topic in topics:
                    checks.append(_read_topic_offsets_check(client=client, topic=topic))
        except Exception as exc:
            return [
                DeleteSafetyCheck(
                    name="topic_offsets",
                    status="warn",
                    detail=f"Kafka metrics client unavailable: {type(exc).__name__}: {exc}",
                )
            ]
        return checks


def _read_topic_offsets_check(
    *, client: KafkaMetricsClient, topic: str
) -> DeleteSafetyCheck:
    try:
        with _timeout_after(
            _TOPIC_OFFSET_CHECK_TIMEOUT_SECONDS,
            reason=f"topic end offset check for {topic}",
        ):
            stats = client.topic_end_offsets_sum(topic)
    except TimeoutError as exc:
        return DeleteSafetyCheck(
            name=f"topic_offsets:{topic}",
            status="warn",
            detail=str(exc),
        )
    except Exception as exc:
        return DeleteSafetyCheck(
            name=f"topic_offsets:{topic}",
            status="warn",
            detail=f"could not read end offsets: {type(exc).__name__}: {exc}",
        )
    if stats.partitions <= 0:
        return DeleteSafetyCheck(
            name=f"topic_offsets:{topic}",
            status="fail",
            detail="topic has no partitions or does not exist",
        )
    status = "pass" if (stats.end_offset_sum or 0) > 0 else "warn"
    detail = f"partitions={stats.partitions}, end_offset_sum={stats.end_offset_sum}"
    if status == "warn":
        detail += " (empty topic; verify source count before deletion)"
    return DeleteSafetyCheck(
        name=f"topic_offsets:{topic}",
        status=status,
        detail=detail,
    )


@contextmanager
def _timeout_after(seconds: float, *, reason: str):
    """Bound best-effort live checks so safety UX never hangs forever."""

    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def _raise_timeout(signum, frame):  # pragma: no cover - signal callback
        raise TimeoutError(f"{reason} timed out after {seconds:g}s")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


@contextmanager
def _suppress_kafka_client_logs():
    """Keep safe-delete output focused on BKKT checks, not broker internals."""

    loggers = [
        logging.getLogger("kafka"),
        logging.getLogger("kafka.conn"),
        logging.getLogger("kafka.client"),
        logging.getLogger("kafka.consumer"),
    ]
    previous = [logger.level for logger in loggers]
    try:
        for logger in loggers:
            logger.setLevel(logging.CRITICAL)
        yield
    finally:
        for logger, level in zip(loggers, previous, strict=True):
            logger.setLevel(level)


def enforce_safe_delete(report: DeleteSafetyReport) -> None:
    if report.failed:
        raise ConfigError(report.failure_message())


def infer_target_topics(cfg: Mapping[str, Any]) -> tuple[str, ...]:
    prefix = str(cfg.get("topic.prefix") or "").strip()
    raw_tables = str(cfg.get("table.include.list") or cfg.get("table.whitelist") or "")
    if not prefix or not raw_tables.strip():
        return ()

    regex = str(cfg.get("transforms.replaceTopicName.regex") or "").strip()
    replacement = str(cfg.get("transforms.replaceTopicName.replacement") or "").strip()

    topics: list[str] = []
    for table in _split_csv(raw_tables):
        if "." not in table:
            continue
        raw_topic = f"{prefix}.{table}"
        target = _apply_java_regex_router(
            raw_topic, regex=regex, replacement=replacement
        )
        if target not in topics:
            topics.append(target)
    return tuple(topics)


def kafka_config_from_connector_config(cfg: Mapping[str, Any]) -> KafkaConfig | None:
    raw_bootstrap = str(cfg.get("bootstrap.servers") or "").strip()
    if not raw_bootstrap:
        return None
    bootstrap = tuple(part.strip() for part in raw_bootstrap.split(",") if part.strip())
    if not bootstrap:
        return None

    mechanism = str(cfg.get("sasl.mechanism") or "").strip() or None
    iam_region = None
    if mechanism and mechanism.upper() == "AWS_MSK_IAM":
        mechanism = "OAUTHBEARER"
        iam_region = _infer_aws_region_from_bootstrap(bootstrap)

    return KafkaConfig(
        bootstrap_servers=bootstrap,
        security_protocol=str(cfg.get("security.protocol") or "").strip() or None,
        sasl_mechanism=mechanism,
        iam_region=iam_region,
    )


def _offset_checks(payload: Mapping[str, Any]) -> list[DeleteSafetyCheck]:
    entries = payload.get("offsets")
    if not isinstance(entries, list) or not entries:
        return [
            DeleteSafetyCheck(
                name="offsets",
                status="fail",
                detail="initial_only connector has no framework offsets",
            )
        ]

    checks: list[DeleteSafetyCheck] = []
    active_markers: list[str] = []
    seen = 0
    latest_parts: list[str] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        offset = entry.get("offset") or {}
        if not isinstance(offset, Mapping):
            continue
        seen += 1
        marker = offset.get("snapshot")
        if _is_active_snapshot_marker(marker):
            active_markers.append(str(marker))
        latest_parts.append(_offset_summary(offset))

    if seen <= 0:
        checks.append(
            DeleteSafetyCheck(
                name="offsets",
                status="fail",
                detail="initial_only connector offsets payload has no usable offset entries",
            )
        )
    elif active_markers:
        checks.append(
            DeleteSafetyCheck(
                name="snapshot_marker",
                status="fail",
                detail=f"active snapshot marker found: {', '.join(active_markers)}",
            )
        )
    else:
        checks.append(
            DeleteSafetyCheck(
                name="snapshot_marker",
                status="pass",
                detail="no active snapshot marker in connector offsets",
            )
        )
        checks.append(
            DeleteSafetyCheck(
                name="offsets",
                status="pass",
                detail="; ".join(part for part in latest_parts if part)
                or f"entries={seen}",
            )
        )
    return checks


def _split_csv(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _apply_java_regex_router(raw_topic: str, *, regex: str, replacement: str) -> str:
    if not regex or not replacement:
        return raw_topic
    py_replacement = re.sub(r"\$(\d+)", r"\\\1", replacement)
    try:
        return re.sub(regex, py_replacement, raw_topic)
    except re.error:
        return raw_topic


def _is_active_snapshot_marker(marker: Any) -> bool:
    if marker is True:
        return True
    if marker is False or marker is None:
        return False
    value = str(marker).strip().lower()
    return value in {"true", "running", "active", "in_progress", "in-progress"}


def _offset_summary(offset: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in ("ts_sec", "ts_ms", "ts_us", "file", "pos", "gtids", "lsn", "txId"):
        value = offset.get(key)
        if value is not None:
            parts.append(f"{key}={value}")
    marker = offset.get("snapshot")
    if marker is not None:
        parts.append(f"snapshot={marker}")
    return ", ".join(parts)


def _infer_aws_region_from_bootstrap(bootstrap: Sequence[str]) -> str | None:
    for server in bootstrap:
        match = re.search(r"\.([a-z]{2}-[a-z]+-\d)\.amazonaws\.com", server)
        if match:
            return match.group(1)
    return None
