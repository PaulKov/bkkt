from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from ..exceptions import KafkaMetricsError
from ..models import KafkaConfig

try:
    from kafka import KafkaAdminClient, KafkaConsumer, TopicPartition
except Exception:  # pragma: no cover
    KafkaAdminClient = None
    KafkaConsumer = None
    TopicPartition = None


def _require_kafka_python() -> None:
    if KafkaAdminClient is None or KafkaConsumer is None or TopicPartition is None:
        raise KafkaMetricsError(
            "kafka-python is not installed. Install it (pip install kafka-python) to enable Kafka metrics."
        )


def common_kafka_client_kwargs(*, cfg: KafkaConfig, client_id: str) -> Dict[str, Any]:
    kw: Dict[str, Any] = {
        "bootstrap_servers": list(cfg.bootstrap_servers),
        "client_id": client_id,
        # Reduce auto-detection delays in CI
        "api_version_auto_timeout_ms": 10000,
        "request_timeout_ms": 20000,
    }
    if cfg.security_protocol:
        kw["security_protocol"] = cfg.security_protocol
    if cfg.sasl_mechanism:
        kw["sasl_mechanism"] = cfg.sasl_mechanism

    # IAM auth (Amazon MSK) uses SASL/OAUTHBEARER for non-Java clients.
    if (
        isinstance(cfg.sasl_mechanism, str)
        and cfg.sasl_mechanism.upper() == "OAUTHBEARER"
    ):
        if not cfg.iam_region:
            raise KafkaMetricsError(
                "KafkaConfig.iam_region is required when sasl_mechanism=OAUTHBEARER (MSK IAM)"
            )
        from .iam import AwsMskIamTokenProvider

        kw["sasl_oauth_token_provider"] = AwsMskIamTokenProvider(
            region=str(cfg.iam_region),
            aws_profile=str(cfg.aws_profile) if cfg.aws_profile else None,
        )
    if cfg.sasl_plain_username is not None:
        kw["sasl_plain_username"] = cfg.sasl_plain_username
    if cfg.sasl_plain_password is not None:
        kw["sasl_plain_password"] = cfg.sasl_plain_password
    if cfg.ssl_cafile:
        kw["ssl_cafile"] = cfg.ssl_cafile
    return kw


@dataclass
class TopicStats:
    topic: str
    partitions: int
    end_offset_sum: Optional[int] = None


@dataclass
class ConsumerLag:
    group_id: str
    topic: str
    lag_sum: Optional[int] = None
    committed_sum: Optional[int] = None
    end_offset_sum: Optional[int] = None


class KafkaMetricsClient:
    """Best-effort Kafka metrics using kafka-python.

    Supports:
    - listing topics
    - message count per topic (sum of end offsets across partitions)
    - consumer group lag (sum over partitions)
    """

    def __init__(self, cfg: KafkaConfig, client_id: str = "connectctl-metrics"):
        _require_kafka_python()
        self.cfg = cfg
        self.client_id = client_id

    def _common_kwargs(self) -> Dict[str, Any]:
        return common_kafka_client_kwargs(cfg=self.cfg, client_id=self.client_id)

    def list_topics(self) -> List[str]:
        kw = self._common_kwargs()
        consumer = KafkaConsumer(enable_auto_commit=False, group_id=None, **kw)
        try:
            return sorted(list(consumer.topics()))
        finally:
            consumer.close()

    def topic_end_offsets_sum(self, topic: str) -> TopicStats:
        kw = self._common_kwargs()
        consumer = KafkaConsumer(enable_auto_commit=False, group_id=None, **kw)
        try:
            parts = consumer.partitions_for_topic(topic) or set()
            tps = [TopicPartition(topic, p) for p in sorted(parts)]
            if not tps:
                return TopicStats(topic=topic, partitions=0, end_offset_sum=0)
            end_offsets = consumer.end_offsets(tps)
            end_sum = sum(int(end_offsets[tp]) for tp in tps)
            return TopicStats(topic=topic, partitions=len(tps), end_offset_sum=end_sum)
        finally:
            consumer.close()

    def consumer_group_lag_sum(
        self, group_id: str, topics: Sequence[str]
    ) -> List[ConsumerLag]:
        """Compute lag per topic for a consumer group.

        If group_id doesn't exist or offsets can't be fetched, returns lag_sum=None.
        """
        kw = self._common_kwargs()
        admin = KafkaAdminClient(**kw)
        consumer = KafkaConsumer(enable_auto_commit=False, group_id=None, **kw)
        try:
            offsets = admin.list_consumer_group_offsets(group_id) or {}
        except Exception:
            # group may not exist
            admin.close()
            consumer.close()
            return [
                ConsumerLag(group_id=group_id, topic=t, lag_sum=None) for t in topics
            ]

        try:
            # Build per-topic TP list
            per_topic: Dict[str, List[TopicPartition]] = {t: [] for t in topics}
            for tp in offsets.keys():
                if tp.topic in per_topic:
                    per_topic[tp.topic].append(tp)

            results: List[ConsumerLag] = []
            for topic, tps in per_topic.items():
                if not tps:
                    results.append(
                        ConsumerLag(group_id=group_id, topic=topic, lag_sum=None)
                    )
                    continue
                end_offsets = consumer.end_offsets(tps)
                end_sum = sum(int(end_offsets[tp]) for tp in tps)
                committed_sum = 0
                for tp in tps:
                    meta = offsets.get(tp)
                    if meta is None or meta.offset is None:
                        # unknown -> treat as 0 committed
                        continue
                    committed_sum += int(meta.offset)
                lag_sum = end_sum - committed_sum
                results.append(
                    ConsumerLag(
                        group_id=group_id,
                        topic=topic,
                        lag_sum=lag_sum,
                        committed_sum=committed_sum,
                        end_offset_sum=end_sum,
                    )
                )
            return results
        finally:
            try:
                admin.close()
            except Exception:
                pass
            consumer.close()
