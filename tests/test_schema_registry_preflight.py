from __future__ import annotations

from pathlib import Path

import pytest

from connectctl.exceptions import ValidationError
from connectctl.models import (
    ConnectorManifest,
    ConnectorPathInfo,
    ConnectorType,
    Environment,
)
from connectctl.services.apply.schema_registry_preflight import (
    run_schema_registry_preflight,
)


def _source_manifest(config: dict[str, object]) -> ConnectorManifest:
    info = ConnectorPathInfo(
        path=Path(
            "/repo/domain/source/postgres/connector_x/prod.x.source.postgres.0.json"
        ),
        relpath=Path(
            "domain/source/postgres/connector_x/prod.x.source.postgres.0.json"
        ),
        domain="domain",
        connector_type=ConnectorType.source,
        system="postgres",
        connector_dir="connector_x",
        env=Environment.prod,
        remainder="x.source.postgres.0",
    )
    return ConnectorManifest(
        name="prod.domain.x.source.postgres.0",
        config=config,
        source_path=info.path,
        info=info,
    )


def test_schema_registry_preflight_blocks_in_place_nullable_standard_migration() -> (
    None
):
    manifest = _source_manifest(
        {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
            "value.converter.schemas.enable": "true",
            "value.converter.ignore.default.for.nullables": "true",
            "value.converter.optional.for.nullables": "true",
            "value.converter.wrapper.for.nullables": "true",
            "value.converter.replace.null.with.default": "false",
        }
    )
    existing = {
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
        "value.converter.schemas.enable": "true",
        "value.converter.ignore.default.for.nullables": "false",
        "value.converter.optional.for.nullables": "false",
        "value.converter.wrapper.for.nullables": "false",
        "value.converter.replace.null.with.default": "true",
    }

    with pytest.raises(ValidationError, match="Schema Registry preflight blocked"):
        run_schema_registry_preflight(
            manifest=manifest,
            existing_config=existing,
            connectctl_meta={},
        )


def test_schema_registry_preflight_allows_new_topics_without_latest_subject() -> None:
    manifest = _source_manifest(
        {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
            "value.converter.schemas.enable": "true",
            "value.converter.ignore.default.for.nullables": "true",
            "value.converter.optional.for.nullables": "true",
            "value.converter.wrapper.for.nullables": "true",
            "value.converter.replace.null.with.default": "false",
        }
    )

    run_schema_registry_preflight(
        manifest=manifest,
        existing_config=None,
        connectctl_meta={},
    )


def test_schema_registry_preflight_requires_complete_migration_plan_for_allowlist() -> (
    None
):
    manifest = _source_manifest(
        {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
            "value.converter.schemas.enable": "true",
            "value.converter.ignore.default.for.nullables": "true",
            "value.converter.optional.for.nullables": "true",
            "value.converter.wrapper.for.nullables": "true",
            "value.converter.replace.null.with.default": "false",
        }
    )
    existing = {
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
        "value.converter.ignore.default.for.nullables": "false",
        "value.converter.optional.for.nullables": "false",
        "value.converter.wrapper.for.nullables": "false",
        "value.converter.replace.null.with.default": "true",
    }

    with pytest.raises(ValidationError, match="migration_plan"):
        run_schema_registry_preflight(
            manifest=manifest,
            existing_config=existing,
            connectctl_meta={
                "schema_registry_preflight": {
                    "allow_in_place_nullable_migration": True,
                    "ticket": "DATAPLAT-1",
                }
            },
        )


def test_schema_registry_preflight_allows_documented_migration_exception() -> None:
    manifest = _source_manifest(
        {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
            "value.converter.schemas.enable": "true",
            "value.converter.ignore.default.for.nullables": "true",
            "value.converter.optional.for.nullables": "true",
            "value.converter.wrapper.for.nullables": "true",
            "value.converter.replace.null.with.default": "false",
        }
    )
    existing = {
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
        "value.converter.ignore.default.for.nullables": "false",
        "value.converter.optional.for.nullables": "false",
        "value.converter.wrapper.for.nullables": "false",
        "value.converter.replace.null.with.default": "true",
    }

    run_schema_registry_preflight(
        manifest=manifest,
        existing_config=existing,
        connectctl_meta={
            "schema_registry_preflight": {
                "allow_in_place_nullable_migration": True,
                "ticket": "DATAPLAT-1",
                "reason": "V2 topic cutover already announced",
                "migration_plan": "docs/runbooks/example.md",
                "subjects": ["cdc.prod.domain.x.table.0-value"],
            }
        },
    )
