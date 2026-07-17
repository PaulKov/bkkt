from __future__ import annotations

from pathlib import Path

from connectctl.models import (
    ConnectorManifest,
    ConnectorPathInfo,
    ConnectorType,
    Environment,
)
from connectctl.services.schema_preflight.models import PreflightDecision
from connectctl.services.schema_preflight.service import SchemaPreflightService


def _source_manifest(
    config: dict[str, object], *, name: str = "prod.domain.x.source.postgres.0"
) -> ConnectorManifest:
    info = ConnectorPathInfo(
        path=Path(
            "/repo/domain/source/postgres/connector/prod.x.source.postgres.0.json"
        ),
        relpath=Path("domain/source/postgres/connector/prod.x.source.postgres.0.json"),
        domain="domain",
        connector_type=ConnectorType.source,
        system="postgres",
        connector_dir="connector",
        env=Environment.prod,
        remainder="x.source.postgres.0",
    )
    return ConnectorManifest(name=name, config=config, source_path=info.path, info=info)


def test_schema_preflight_blocks_nullable_and_topic_prefix_risks() -> None:
    service = SchemaPreflightService()
    manifest = _source_manifest(
        {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
            "value.converter.ignore.default.for.nullables": "true",
            "value.converter.optional.for.nullables": "true",
            "value.converter.wrapper.for.nullables": "true",
            "value.converter.replace.null.with.default": "false",
            "topic.prefix": "new.prefix",
        }
    )
    existing = {
        "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
        "value.converter.ignore.default.for.nullables": "false",
        "value.converter.optional.for.nullables": "false",
        "value.converter.wrapper.for.nullables": "false",
        "value.converter.replace.null.with.default": "true",
        "topic.prefix": "old.prefix",
    }

    result = service.analyze(manifest=manifest, existing_config=existing)

    assert result.decision is PreflightDecision.block
    assert result.mode == "risk-analyzer-only"
    assert {risk.risk_id for risk in result.risks} >= {
        "protobuf_nullable_semantics_change",
        "topic_prefix_or_subject_namespace_change",
    }


def test_schema_preflight_allows_documented_non_expired_allowlist() -> None:
    service = SchemaPreflightService(
        repo_allowlist=[
            {
                "connector": "prod.domain.x.source.postgres.0",
                "risk_id": "topic_prefix_or_subject_namespace_change",
                "adr": "docs/adr/0001.md",
                "owner": "data-platform",
                "expires_at": "2999-01-01",
                "reason": "V2 topic namespace migration",
            }
        ]
    )
    manifest = _source_manifest(
        {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
            "topic.prefix": "new.prefix",
        }
    )

    result = service.analyze(
        manifest=manifest,
        existing_config={
            "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
            "topic.prefix": "old.prefix",
        },
    )

    assert result.decision is PreflightDecision.warn
    assert result.risks[0].allowed is True
    assert result.risks[0].allowlist_entry is not None


def test_schema_preflight_expired_allowlist_does_not_allow_risk() -> None:
    service = SchemaPreflightService(
        repo_allowlist=[
            {
                "connector": "prod.domain.x.source.postgres.0",
                "risk_id": "topic_prefix_or_subject_namespace_change",
                "adr": "docs/adr/0001.md",
                "owner": "data-platform",
                "expires_at": "2020-01-01",
                "reason": "Old migration",
            }
        ]
    )
    manifest = _source_manifest(
        {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
            "topic.prefix": "new.prefix",
        }
    )

    result = service.analyze(
        manifest=manifest,
        existing_config={
            "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
            "topic.prefix": "old.prefix",
        },
    )

    assert result.decision is PreflightDecision.block
    assert result.risks[0].allowed is False


def test_schema_preflight_reports_exact_mode_when_candidate_schema_is_available(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "subject.proto"
    candidate.write_text(
        'syntax = "proto3"; message Value { string id = 1; }\n', encoding="utf-8"
    )
    service = SchemaPreflightService()
    manifest = _source_manifest(
        {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
        }
    )

    result = service.analyze(
        manifest=manifest,
        existing_config={
            "value.converter": "io.confluent.connect.protobuf.ProtobufConverter"
        },
        candidate_schema_files={"subject-value": candidate},
    )

    assert result.decision is PreflightDecision.pass_
    assert result.mode == "mixed"
    assert result.exact_checks[0]["subject"] == "subject-value"
    assert result.exact_checks[0]["status"] == "candidate-schema-loaded"
