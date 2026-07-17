from __future__ import annotations

from typing import Any, Optional

from ...kafka import KafkaMetricsClient
from ...logging_utils import get_logger


def build_kafka_metrics_client(
    cluster: Any,
    *,
    enabled: bool,
    logger=None,
) -> Optional[KafkaMetricsClient]:
    """Best-effort KafkaMetricsClient init for smoke checks."""

    log = get_logger(logger)

    if not enabled:
        return None

    kafka_cfg = getattr(cluster, "kafka", None)
    if kafka_cfg is None:
        return None

    try:
        return KafkaMetricsClient(kafka_cfg)
    except Exception as e:
        log.warning("Kafka smoke checks disabled (cannot init Kafka client): %s", e)
        return None
