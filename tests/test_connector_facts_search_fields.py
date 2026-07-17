from __future__ import annotations

from connectctl.services.connector_facts import (
    build_connector_facts_from_live_config,
    extract_sink_database_from_config,
    extract_sink_table_full_names_from_config,
    extract_sink_tables_from_config,
    extract_topic_patterns_from_config,
)


def test_explicit_iceberg_route_config_populates_searchable_table_facts() -> None:
    cfg = {
        "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
        "iceberg.table.prod__dbt__acme__orders__raw.daily_aggregated_exchange_rates__events.route-regex": "^acme\\.orders\\.daily_aggregated_exchange_rates$",
        "iceberg.table.prod__dbt__acme__orders__raw.exchange_rates__events.route-regex": "^acme\\.orders\\.exchange_rates$",
        "iceberg.tables": "prod__dbt__acme__orders__raw.exchange_rates__events,prod__dbt__acme__orders__raw.daily_aggregated_exchange_rates__events",
    }

    assert extract_sink_database_from_config(cfg) == ("prod__dbt__acme__orders__raw")
    assert extract_sink_tables_from_config(cfg) == [
        "daily_aggregated_exchange_rates__events",
        "exchange_rates__events",
    ]
    assert extract_sink_table_full_names_from_config(cfg) == (
        "prod__dbt__acme__orders__raw.daily_aggregated_exchange_rates__events",
        "prod__dbt__acme__orders__raw.exchange_rates__events",
    )
    assert extract_topic_patterns_from_config(cfg) == (
        "^acme\\.orders\\.daily_aggregated_exchange_rates$",
        "^acme\\.orders\\.exchange_rates$",
    )


def test_connector_facts_query_fields_include_full_iceberg_tables_and_patterns() -> (
    None
):
    facts = build_connector_facts_from_live_config(
        name="prod.acme.orders.sink.raw.iceberg.2",
        cfg={
            "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
            "iceberg.table.prod__dbt__acme__orders__raw.exchange_rates__events.route-regex": "^acme\\.orders\\.exchange_rates$",
            "iceberg.tables": "prod__dbt__acme__orders__raw.exchange_rates__events",
        },
        envs=("prod",),
        clusters=("acme-external",),
        alias_scopes=(),
    )

    fields = facts.query_fields()
    assert fields["tables.sink"] == ("exchange_rates__events",)
    assert fields["tables.sink_full"] == (
        "prod__dbt__acme__orders__raw.exchange_rates__events",
    )
    assert fields["sink.database"] == ("prod__dbt__acme__orders__raw",)
    assert fields["topics.pattern"] == ("^acme\\.orders\\.exchange_rates$",)
    assert fields["topics.any"] == ("^acme\\.orders\\.exchange_rates$",)


def test_topic2table_map_populates_consumed_topics_for_sink_without_topics_key() -> (
    None
):
    facts = build_connector_facts_from_live_config(
        name="prod.acme.events.sink.raw.clickhouse.0",
        cfg={
            "connector.class": "com.clickhouse.kafka.connect.ClickHouseSinkConnector",
            "topic2TableMap": "acme.events=events_raw",
        },
        envs=("prod",),
        clusters=("acme-external",),
        alias_scopes=(),
    )

    assert facts.consumed_topics == ("acme.events",)
    assert facts.sink_tables == ("events_raw",)
    assert facts.query_fields()["topics.any"] == ("acme.events",)
