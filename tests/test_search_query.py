from __future__ import annotations

from argparse import Namespace

import pytest

from connectctl.cli_parser import build_parser
from connectctl.exceptions import ConfigError
from connectctl.services.connector_facts import ConnectorFacts
from connectctl.services.search.evaluator import SearchEvaluator
from connectctl.services.search.models import (
    SearchAnd,
    SearchFieldRef,
    SearchLeaf,
    SearchOperator,
    SearchOr,
    SearchSource,
    SearchView,
)
from connectctl.services.search.query import build_search_query, parse_where_clause


def _facts(**overrides) -> ConnectorFacts:
    base = ConnectorFacts(
        name="prod.payments.payments_prod.source.postgres.0",
        origin="repo",
        path="connectors/payments/source/postgres/connector_payments__payments_prod/prod.payments.payments_prod.source.postgres.0.json",
        envs=("prod",),
        clusters=("acme-main",),
        alias_scopes=(),
        domain="payments",
        dataset="payments_prod",
        connector_type="source",
        system="postgres",
        layer=None,
        mode=None,
        kind=None,
        source_tables=("invoice_items", "payments"),
        sink_tables=(),
        consumed_topics=(),
        produced_topics=("prod.payments.payments_prod.source.postgres.0.topic",),
        produced_pattern=None,
        db_hosts=("pg.prod.internal",),
        db_ports=("5432",),
        db_names=("payments_prod",),
        db_schemas=("billing",),
        db_servers=("payments_publication",),
        sink_database=None,
        sink_warehouse=None,
        config={
            "database.hostname": "pg.prod.internal",
            "table.include.list": "invoice_items,payments",
            "topic.prefix": "prod.payments.payments_prod.source.postgres.0.changes",
        },
    )
    return ConnectorFacts(**{**base.__dict__, **overrides})


def test_search_parser_accepts_search_and_find_alias() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "search",
            "--source",
            "both",
            "--env",
            "all",
            "--cluster",
            "all",
            "--view",
            "long",
            "--type",
            "source",
            "--topic",
            "a,b",
            "--name-fuzzy",
            "prod.demo.sink.icebrg.0",
        ]
    )
    assert args.cmd == "search"
    assert args.source == "both"
    assert args.env == "all"
    assert args.cluster == "all"
    assert args.view == "long"
    assert args.connector_type == ["source"]
    assert args.name_fuzzy == ["prod.demo.sink.icebrg.0"]

    alias_args = parser.parse_args(["find", "--name", "prod.demo.source.file.0"])
    assert alias_args.cmd == "find"
    assert alias_args.name == ["prod.demo.source.file.0"]
    assert alias_args.view == "long"
    assert alias_args.explain == "long"


def test_search_parser_uses_parallel_default_jobs() -> None:
    parser = build_parser()

    args = parser.parse_args(["search", "--topic", "demo.topic"])
    assert args.jobs == 8

    alias_args = parser.parse_args(["find", "--name", "prod.demo.source.file.0"])
    assert alias_args.jobs == 8


def test_build_search_query_combines_common_flags_and_where() -> None:
    args = Namespace(
        source="both",
        env="all",
        cluster="all",
        view="long",
        limit=25,
        ignore_case=True,
        name=["prod.payments.payments_prod.source.postgres.0"],
        name_prefix=[],
        name_suffix=[],
        name_regexp=[],
        table=["invoice_items,payments"],
        table_prefix=[],
        table_suffix=[],
        table_regexp=[],
        table_match="all",
        topic=[],
        topic_prefix=["prod.payments."],
        topic_suffix=[],
        topic_regexp=[],
        topic_match="any",
        domain=["payments"],
        dataset=[],
        connector_type=["source"],
        system=["postgres"],
        layer=[],
        mode=[],
        kind=[],
        host=["pg.prod.internal"],
        database=[],
        schema=[],
        server=[],
        has_config_key=["table.include.list"],
        config_eq=["database.hostname=pg.prod.internal"],
        config_prefix=[],
        config_suffix=[],
        config_regexp=[],
        where=['exists(config("topic.prefix")) AND NOT env = stage'],
    )

    query = build_search_query(args)
    assert query.source is SearchSource.both
    assert query.envs == ("dev", "stage", "prod")
    assert query.cluster_filter is None
    assert query.view is SearchView.long
    assert query.limit == 25
    assert query.ignore_case is True
    assert query.where_clauses == (
        'exists(config("topic.prefix")) AND NOT env = stage',
    )
    assert isinstance(query.expression, SearchAnd)


def test_parse_where_clause_supports_boolean_grammar_and_config_access() -> None:
    expr = parse_where_clause(
        'exists(config("table.include.list")) AND (db.host = "pg.prod.internal" OR name ^= "prod.payments")'
    )
    assert isinstance(expr, SearchAnd)
    assert isinstance(expr.items[1], SearchOr)


def test_parse_where_clause_rejects_unknown_field() -> None:
    with pytest.raises(ConfigError, match="Unsupported search field"):
        parse_where_clause("unknown.field = x")


def test_search_evaluator_matches_boolean_and_config_predicates() -> None:
    expr = parse_where_clause(
        'exists(config("table.include.list")) AND db.host = "pg.prod.internal" AND NOT env = stage'
    )
    result = SearchEvaluator(ignore_case=False).evaluate(expr, facts=_facts())
    assert result.matched is True
    assert any(item.field == 'config("table.include.list")' for item in result.details)
    assert any(item.field == "db.host" for item in result.details)


def test_search_evaluator_honors_ignore_case_for_exact_prefix_suffix_and_regex() -> (
    None
):
    facts = _facts(name="PROD.Payments.Payments_Prod.Source.Postgres.0")
    exact = parse_where_clause('name = "prod.payments.payments_prod.source.postgres.0"')
    prefix = parse_where_clause('name ^= "prod.payments"')
    suffix = parse_where_clause('name $= "postgres.0"')
    regex = parse_where_clause('name ~= "^prod\\\\.payments\\\\..+postgres\\\\.0$"')

    evaluator = SearchEvaluator(ignore_case=True)
    assert evaluator.evaluate(exact, facts=facts).matched is True
    assert evaluator.evaluate(prefix, facts=facts).matched is True
    assert evaluator.evaluate(suffix, facts=facts).matched is True
    assert evaluator.evaluate(regex, facts=facts).matched is True


def test_search_evaluator_matches_full_sink_table_name() -> None:
    facts = _facts(
        connector_type="sink",
        system="iceberg",
        source_tables=(),
        sink_tables=("invoice_items__events",),
        sink_database="prod__dbt__payments__payments_prod__raw",
        config={
            "transforms.setTableName.db.name": "prod__dbt__payments__payments_prod__raw",
            "iceberg.table.prod__dbt__payments__payments_prod__raw.invoice_items__events.id-columns": "id",
        },
    )
    expr = parse_where_clause(
        'tables.sink_full = "prod__dbt__payments__payments_prod__raw.invoice_items__events"'
    )

    result = SearchEvaluator(ignore_case=False).evaluate(expr, facts=facts)
    assert result.matched is True
    assert any(item.field == "tables.sink_full" for item in result.details)


def test_search_evaluator_matches_exact_topic_against_topic_pattern_only() -> None:
    facts = _facts(
        connector_type="sink",
        system="iceberg",
        consumed_topics=(),
        produced_topics=(),
        config={
            "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
            "iceberg.table.prod__dbt__acme__orders__raw.exchange_rates__events.route-regex": "^acme\\.orders\\.exchange_rates$",
            "iceberg.tables": "prod__dbt__acme__orders__raw.exchange_rates__events",
        },
    )

    matched = parse_where_clause('topics.pattern = "acme.orders.exchange_rates"')
    missed = parse_where_clause('topics.pattern = "acme.orders.fx"')

    evaluator = SearchEvaluator(ignore_case=False)
    assert evaluator.evaluate(matched, facts=facts).matched is True
    assert evaluator.evaluate(missed, facts=facts).matched is False


def test_search_evaluator_matches_fuzzy_connector_name() -> None:
    facts = _facts(name="prod.acme.orders.sink.raw.iceberg.2")
    expr = parse_where_clause('name ~= "prod\\.acme\\..+"')
    assert SearchEvaluator(ignore_case=False).evaluate(expr, facts=facts).matched

    fuzzy = SearchOr(
        items=(
            SearchLeaf(
                fields=(SearchFieldRef("name"),),
                operator=SearchOperator.fuzzy,
                values=("prod.acme.orders_exchnage.sink.raw.iceberg.2",),
            ),
        )
    )
    assert SearchEvaluator(ignore_case=False).evaluate(fuzzy, facts=facts).matched


def test_search_evaluator_expands_variables_per_connector() -> None:
    facts = _facts(
        connector_type="sink",
        system="iceberg",
        sink_tables=("exchange_rates__events",),
        sink_database="prod__dbt__acme__orders__raw",
        config={
            "iceberg.tables": "prod__dbt__acme__orders__raw.exchange_rates__events",
        },
    )
    expr = parse_where_clause('tables.sink_full = "${sink.full_table}"')

    result = SearchEvaluator(ignore_case=False).evaluate(expr, facts=facts)
    assert result.matched is True
    assert result.details[0].query_value == (
        "prod__dbt__acme__orders__raw.exchange_rates__events"
    )
