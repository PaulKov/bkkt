from __future__ import annotations

from pathlib import Path

from connectctl.models import (
    ConnectorManifest,
    ConnectorPathInfo,
    ConnectorType,
    Environment,
)
from connectctl.validation.policies import lint_policies


def _mk_source_manifest(
    *, name: str, env: Environment, config: dict
) -> ConnectorManifest:
    p = Path(f"/tmp/{name}.json")
    info = ConnectorPathInfo(
        path=p,
        relpath=Path(f"x/{name}.json"),
        domain="gamemode",
        connector_type=ConnectorType.source,
        system="postgres",
        connector_dir="connector_gamemode",
        env=env,
        remainder="",
        mode="cdc",
    )
    return ConnectorManifest(name=name, config=config, source_path=p, info=info)


def _mk_sink_manifest(
    *, name: str, env: Environment, config: dict
) -> ConnectorManifest:
    p = Path(f"/tmp/{name}.json")
    info = ConnectorPathInfo(
        path=p,
        relpath=Path(f"x/{name}.json"),
        domain="cash",
        connector_type=ConnectorType.sink,
        system="iceberg",
        connector_dir="connector_cash_service",
        env=env,
        remainder="",
        mode=None,
    )
    return ConnectorManifest(name=name, config=config, source_path=p, info=info)


def test_foreign_env_reference_does_not_false_positive_on_postgres_contains_stg() -> (
    None
):
    # Regression: 'postgres' contains substring 'stg', but it's not a stage env reference.
    env = Environment.prod

    name = "prod.gamemode.gamemode.source.postgres.cdc.2"
    m = _mk_source_manifest(
        name=name,
        env=env,
        config={
            "name": name,
            "topic.prefix": "prod.gamemode.gamemode.source.postgres.cdc.2.changes",
            "schema.history.internal.kafka.topic": "prod.gamemode.gamemode.source.postgres.cdc.2.history",
            "transforms.replaceTopicName.regex": "prod.gamemode.gamemode.source.postgres.cdc.2.changes\\.([^.]+)\\.(.*)",
        },
    )

    issues = lint_policies(m, env=env, layers=None)
    assert not any(i.policy == "FOREIGN_ENV_REFERENCE" for i in issues)


def test_foreign_env_reference_catches_real_stg_token_in_prod() -> None:
    env = Environment.prod

    name = "prod.gamemode.gamemode.source.postgres.cdc.0"
    m = _mk_source_manifest(
        name=name,
        env=env,
        config={
            "name": name,
            "iceberg.catalog.warehouse": "s3://bucket-stg1/warehouse",
        },
    )

    issues = lint_policies(m, env=env, layers=None)
    assert any(i.policy == "FOREIGN_ENV_REFERENCE" for i in issues)


def test_foreign_env_reference_does_not_false_positive_on_topic_with_schema_name_stage() -> (
    None
):
    env = Environment.prod

    name = "prod.cash.cash_service.sink.raw.iceberg.1"
    m = _mk_sink_manifest(
        name=name,
        env=env,
        config={
            "name": name,
            "topics": "cdc.prod.cash.cash_service.cash-stage.agents.0,cdc.prod.cash.cash_service.cash-stage.deposits.0",
        },
    )

    issues = lint_policies(m, env=env, layers=None)
    assert not any(i.policy == "FOREIGN_ENV_REFERENCE" for i in issues)


def test_foreign_env_reference_does_not_false_positive_on_dataset_suffix_prod() -> None:
    env = Environment.stage

    name = "stage.payments.payments_prod.source.postgres.8"
    m = _mk_source_manifest(
        name=name,
        env=env,
        config={
            "name": name,
            "topic.prefix": "stage.payments.payments_prod.source.postgres.0.changes",
            "schema.history.internal.kafka.topic": "stage.payments.payments_prod.source.postgres.0.history",
            "transforms.replaceTopicName.regex": "stage.payments.payments_prod.source.postgres.0.changes\\.([^.]+)\\.(.*)",
            "transforms.replaceTopicName.replacement": "cdc.stage.payments.payments_prod.$1.$2.1",
            "iceberg.control.topic": "stage.payments.payments_prod.sink.raw.iceberg.1.control",
        },
    )

    issues = lint_policies(m, env=env, layers=None)
    assert not any(i.policy == "FOREIGN_ENV_REFERENCE" for i in issues)


def test_foreign_env_reference_still_catches_wrong_topic_env_prefix() -> None:
    env = Environment.prod

    name = "prod.bonus.bonus_common.sink.raw.iceberg.0"
    m = _mk_sink_manifest(
        name=name,
        env=env,
        config={
            "name": name,
            "topics": "cdc.stage.bonus.bonus_common.money_cases.ma_cases_stats.0",
        },
    )

    issues = lint_policies(m, env=env, layers=None)
    assert any(i.policy == "FOREIGN_ENV_REFERENCE" for i in issues)


def test_foreign_env_reference_does_not_false_positive_on_stage_warehouse_with_prod_dataset() -> (
    None
):
    env = Environment.stage

    name = "stage.payments.payments_prod.sink.raw.iceberg.1"
    m = _mk_sink_manifest(
        name=name,
        env=env,
        config={
            "name": name,
            "iceberg.catalog.glue.warehouse": "s3://acme-stage-data/iceberg/lakehouse/cdc/payments/payments_prod/raw/",
        },
    )

    issues = lint_policies(m, env=env, layers=None)
    assert not any(i.policy == "FOREIGN_ENV_REFERENCE" for i in issues)
