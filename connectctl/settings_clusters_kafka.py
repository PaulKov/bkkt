from __future__ import annotations

from typing import Any, Mapping, Optional

from .models import KafkaConfig


def parse_kafka_config(kafka_cfg_obj: Any) -> Optional[KafkaConfig]:
    """Разобрать секцию kafka (опционально).

    Kafka конфиг используется только для метрик/репортинга (KafkaMetricsClient).
    Для Kafka Connect (REST) достаточно секции connect.
    """
    if not isinstance(kafka_cfg_obj, Mapping):
        return None

    bs = kafka_cfg_obj.get("bootstrap_servers") or []
    if isinstance(bs, str):
        bs = [x.strip() for x in bs.split(",") if x.strip()]
    if not bs:
        return None

    # Backwards-compatible flat keys
    security_protocol = kafka_cfg_obj.get("security_protocol")
    sasl_mechanism = kafka_cfg_obj.get("sasl_mechanism")
    sasl_plain_username = kafka_cfg_obj.get("sasl_plain_username")
    sasl_plain_password = kafka_cfg_obj.get("sasl_plain_password")
    ssl_cafile = kafka_cfg_obj.get("ssl_cafile")
    iam_region = kafka_cfg_obj.get("iam_region")
    aws_profile = kafka_cfg_obj.get("aws_profile")

    # New structured auth block
    auth_obj = kafka_cfg_obj.get("auth")
    if isinstance(auth_obj, Mapping):
        auth_type = str(auth_obj.get("type", "")).strip().lower()

        if auth_type in {"iam", "aws_iam", "msk_iam"}:
            # AWS MSK IAM for Python: SASL_SSL + OAUTHBEARER token provider
            iam_region = auth_obj.get("region") or iam_region
            aws_profile = auth_obj.get("aws_profile") or aws_profile
            security_protocol = (
                auth_obj.get("security_protocol") or security_protocol or "SASL_SSL"
            )
            sasl_mechanism = (
                auth_obj.get("mechanism") or sasl_mechanism or "OAUTHBEARER"
            )

        elif auth_type in {"sasl", "sasl_plain", "plain", "username_password"}:
            security_protocol = auth_obj.get("security_protocol") or security_protocol
            sasl_mechanism = auth_obj.get("mechanism") or sasl_mechanism or "PLAIN"
            sasl_plain_username = auth_obj.get("username") or sasl_plain_username
            sasl_plain_password = auth_obj.get("password") or sasl_plain_password
            ssl_cafile = auth_obj.get("ssl_cafile") or ssl_cafile

        elif auth_type in {"sasl_scram", "scram"}:
            security_protocol = auth_obj.get("security_protocol") or security_protocol
            sasl_mechanism = (
                auth_obj.get("mechanism") or sasl_mechanism or "SCRAM-SHA-512"
            )
            sasl_plain_username = auth_obj.get("username") or sasl_plain_username
            sasl_plain_password = auth_obj.get("password") or sasl_plain_password
            ssl_cafile = auth_obj.get("ssl_cafile") or ssl_cafile

    # Convenience: some people may set AWS_MSK_IAM because it's used by JVM clients.
    if isinstance(sasl_mechanism, str) and sasl_mechanism.upper() == "AWS_MSK_IAM":
        sasl_mechanism = "OAUTHBEARER"

    return KafkaConfig(
        bootstrap_servers=list(bs),
        security_protocol=security_protocol,
        sasl_mechanism=sasl_mechanism,
        sasl_plain_username=sasl_plain_username,
        sasl_plain_password=sasl_plain_password,
        ssl_cafile=ssl_cafile,
        iam_region=iam_region,
        aws_profile=aws_profile,
    )
