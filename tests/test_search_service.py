from __future__ import annotations

import builtins
import logging
from dataclasses import dataclass, field
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

import yaml

from connectctl.adapters.filesystem import LocalFileSystem
from connectctl.cli_parser import build_parser
from connectctl.config_models import (
    ExportConfig,
    NamingConfig,
    SafetyConfig,
    SyncConfig,
)
from connectctl.models import ConnectClusterConfig, Environment, RepoConfig
from connectctl.services.search import SearchService
from connectctl.settings_models import Settings, TagSettings


class _FakeConnect:
    def __init__(self, configs: Dict[str, Dict[str, Any]]) -> None:
        self._configs = dict(configs)
        self.list_calls = 0
        self.config_calls: list[str] = []

    def list_connectors(self):
        self.list_calls += 1
        return list(self._configs.keys())

    def get_config_optional(self, name: str) -> Optional[Dict[str, Any]]:
        self.config_calls.append(name)
        return self._configs.get(name)


@dataclass
class _DummyCtx:
    repo_root: Path
    settings: Settings
    logger: logging.Logger
    fs: LocalFileSystem
    live_configs_by_url: Dict[tuple[str, ...], Dict[str, Dict[str, Any]]]
    connect_calls: list[tuple[str, str]] = field(default_factory=list)
    connect_clients: list[_FakeConnect] = field(default_factory=list)

    def connect_target(
        self, env: Environment, cluster_name: str | None, *, throttle=None, timeout=None
    ):
        group = cluster_name or self.settings.default_cluster
        cluster = self.settings.cluster_groups[group][env]
        urls = tuple(str(url) for url in cluster.urls)
        self.connect_calls.append((group, env.value))
        client = _FakeConnect(self.live_configs_by_url.get(urls, {}))
        self.connect_clients.append(client)
        return SimpleNamespace(
            env=env,
            cluster=cluster,
            client=client,
        )


def _logger(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    if not any(isinstance(h, logging.NullHandler) for h in log.handlers):
        log.addHandler(logging.NullHandler())
    log.setLevel(logging.INFO)
    return log


def _make_settings(repo_root: Path) -> Settings:
    repo_cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    main = {
        Environment.dev: ConnectClusterConfig(
            env=Environment.dev,
            urls=("http://dev.shared:8083",),
            kafka=None,
            name="acme-main",
        ),
        Environment.stage: ConnectClusterConfig(
            env=Environment.stage,
            urls=("http://stage.main:8083",),
            kafka=None,
            name="acme-main",
        ),
        Environment.prod: ConnectClusterConfig(
            env=Environment.prod,
            urls=("http://prod.main:8083",),
            kafka=None,
            name="acme-main",
        ),
    }
    source = {
        Environment.dev: ConnectClusterConfig(
            env=Environment.dev,
            urls=("http://dev.shared:8083",),
            kafka=None,
            name="acme-source",
        ),
        Environment.stage: ConnectClusterConfig(
            env=Environment.stage,
            urls=("http://stage.source:8083",),
            kafka=None,
            name="acme-source",
        ),
        Environment.prod: ConnectClusterConfig(
            env=Environment.prod,
            urls=("http://prod.source:8083",),
            kafka=None,
            name="acme-source",
        ),
    }
    external = {
        env: ConnectClusterConfig(
            env=env,
            urls=(f"http://{env.value}.external:8083",),
            kafka=None,
            name="acme-external",
        )
        for env in Environment
    }
    return Settings(
        repo=repo_cfg,
        clusters={env: main[env] for env in Environment},
        cluster_groups={
            "acme-main": main,
            "acme-source": source,
            "acme-external": external,
        },
        default_cluster="acme-main",
        tags=TagSettings(),
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={"enabled": False, "rules": []},
    )


def _write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _build_ctx(tmp_path: Path) -> _DummyCtx:
    settings = _make_settings(tmp_path)
    live_configs = {
        ("http://dev.shared:8083",): {
            "dev.payments.payments_prod.source.postgres.0": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "pg.dev.internal",
                "database.port": "5432",
                "database.dbname": "payments_prod",
                "schema.include.list": "billing",
                "table.include.list": "invoice_items,payments",
                "topic.prefix": "dev.payments.payments_prod.source.postgres.0.changes",
            },
            "dev.payments.payments_prod.sink.raw.iceberg.cdc.events.dbt.0": {
                "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
                "topics": "cdc.dev.payments.payments_prod.pg.invoice_items.dbt.0,cdc.dev.payments.payments_prod.pg.payments.dbt.0",
                "transforms.setTableName.table.suffix": "events",
                "transforms.setTableName.db.name": "dev__dbt__payments__payments_prod__raw",
                "transforms.setTableName.type": "com.example.kafka.connect.transforms.SetTableNameToRouteField",
                "iceberg.table.dev__dbt__payments__payments_prod__raw.invoice_items__events.id-columns": "id",
            },
        },
        ("http://prod.source:8083",): {
            "prod.user_finance.acme_common.source.mariadb.0": {
                "connector.class": "io.debezium.connector.mysql.MySqlConnector",
                "database.hostname": "mariadb.prod.internal",
                "database.port": "3306",
                "database.include.list": "acme_common",
                "table.include.list": "acme_common.ma_balance",
                "topic.prefix": "prod.user_finance.acme_common.source.mariadb.0",
            },
        },
        ("http://prod.external:8083",): {
            "prod.acme.orders.sink.raw.iceberg.2": {
                "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
                "iceberg.catalog.type": "glue",
                "iceberg.catalog.glue.warehouse": "s3://acme-prod-data/iceberg/lakehouse/raw/acme/orders/",
                "iceberg.table.prod__dbt__acme__orders__raw.daily_aggregated_exchange_rates__events.route-regex": "^acme\\.orders\\.daily_aggregated_exchange_rates$",
                "iceberg.table.prod__dbt__acme__orders__raw.exchange_rates__events.route-regex": "^acme\\.orders\\.exchange_rates$",
                "iceberg.tables": "prod__dbt__acme__orders__raw.exchange_rates__events,prod__dbt__acme__orders__raw.daily_aggregated_exchange_rates__events",
            },
            "prod.acme.events.sink.raw.clickhouse.0": {
                "connector.class": "com.clickhouse.kafka.connect.ClickHouseSinkConnector",
                "topic2TableMap": "acme.events=events_raw",
            },
        },
    }
    return _DummyCtx(
        repo_root=tmp_path,
        settings=settings,
        logger=_logger(f"search-service-{tmp_path.name}"),
        fs=LocalFileSystem(),
        live_configs_by_url=live_configs,
    )


def _write_repo_manifests(tmp_path: Path) -> None:
    _write(
        tmp_path
        / "payments/source/postgres/connector_payments__payments_prod/prod.payments.payments_prod.source.postgres.0.json",
        {
            "name": "prod.payments.payments_prod.source.postgres.0",
            "connectctl": {"cluster": "acme-main"},
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "pg.prod.internal",
                "database.port": "5432",
                "database.dbname": "payments_prod",
                "schema.include.list": "billing",
                "table.include.list": "invoice_items,payments",
                "topic.prefix": "prod.payments.payments_prod.source.postgres.0.changes",
            },
        },
    )
    _write(
        tmp_path
        / "payments/sink/iceberg/connector_payments__payments_prod/prod.payments.payments_prod.sink.raw.iceberg.cdc.events.dbt.0.json",
        {
            "name": "prod.payments.payments_prod.sink.raw.iceberg.cdc.events.dbt.0",
            "connectctl": {"cluster": "acme-external"},
            "config": {
                "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
                "topics": "cdc.prod.payments.payments_prod.pg.invoice_items.dbt.0,cdc.prod.payments.payments_prod.pg.payments.dbt.0",
                "transforms.setTableName.table.suffix": "events",
                "transforms.setTableName.db.name": "prod__dbt__payments__payments_prod__raw",
                "transforms.setTableName.type": "com.example.kafka.connect.transforms.SetTableNameToRouteField",
                "iceberg.catalog.glue.warehouse": "s3://acme-prod/iceberg/lakehouse/orders/raw",
            },
        },
    )
    _write(
        tmp_path
        / "payments/source/postgres/connector_payments__payments_prod/dev.payments.payments_prod.source.postgres.0.json",
        {
            "name": "dev.payments.payments_prod.source.postgres.0",
            "connectctl": {"cluster": "acme-main"},
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "pg.dev.internal",
                "database.port": "5432",
                "database.dbname": "payments_prod",
                "schema.include.list": "billing",
                "table.include.list": "invoice_items,payments",
                "topic.prefix": "dev.payments.payments_prod.source.postgres.0.changes",
            },
        },
    )
    _write(
        tmp_path
        / "acme/sink/clickhouse/connector_acme__events/prod.acme.events.sink.raw.clickhouse.0.json",
        {
            "name": "prod.acme.events.sink.raw.clickhouse.0",
            "connectctl": {"cluster": "acme-external"},
            "config": {
                "connector.class": "com.clickhouse.kafka.connect.ClickHouseSinkConnector",
                "topic2TableMap": "acme.events=events_raw",
            },
        },
    )


def _write_acme_orders_iceberg_route_manifest(tmp_path: Path) -> None:
    _write(
        tmp_path
        / "acme/sink/iceberg/connector_acme__orders/prod.acme.orders.sink.raw.iceberg.2.json",
        {
            "name": "prod.acme.orders.sink.raw.iceberg.2",
            "connectctl": {"cluster": "acme-external"},
            "config": {
                "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
                "iceberg.catalog.type": "glue",
                "iceberg.catalog.glue.warehouse": "s3://acme-prod-data/iceberg/lakehouse/raw/acme/orders/",
                "iceberg.table.prod__dbt__acme__orders__raw.daily_aggregated_exchange_rates__events.route-regex": "^acme\\.orders\\.daily_aggregated_exchange_rates$",
                "iceberg.table.prod__dbt__acme__orders__raw.exchange_rates__events.route-regex": "^acme\\.orders\\.exchange_rates$",
                "iceberg.tables": "prod__dbt__acme__orders__raw.exchange_rates__events,prod__dbt__acme__orders__raw.daily_aggregated_exchange_rates__events",
            },
        },
    )


def test_search_service_repo_searches_rendered_manifests_and_cluster_filter(
    tmp_path: Path, capsys
) -> None:
    _write_repo_manifests(tmp_path)
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    args = parser.parse_args(
        [
            "search",
            "--source",
            "repo",
            "--env",
            "prod",
            "--cluster",
            "acme-external",
            "--type",
            "sink",
            "--table-prefix",
            "invoice_items",
            "--output",
            "json",
        ]
    )
    rc = SearchService(ctx=ctx, logger=ctx.logger).run(args)
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    result = payload["results"][0]
    assert result["origin"] == "repo"
    assert (
        result["name"]
        == "prod.payments.payments_prod.sink.raw.iceberg.cdc.events.dbt.0"
    )
    assert result["cluster"] == ["acme-external"]
    assert "invoice_items__events" in result["tables"]["sink"]
    assert any(item["field"] == "tables.sink" for item in result["matched"])


def test_search_service_repo_long_text_includes_details(tmp_path: Path, capsys) -> None:
    _write_repo_manifests(tmp_path)
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    args = parser.parse_args(
        [
            "search",
            "--source",
            "repo",
            "--env",
            "prod",
            "--view",
            "long",
            "--where",
            'exists(config("table.include.list")) AND db.host = "pg.prod.internal"',
        ]
    )
    rc = SearchService(ctx=ctx, logger=ctx.logger).run(args)
    assert rc == 0

    out = capsys.readouterr().out
    assert "Connector: prod.payments.payments_prod.source.postgres.0" in out
    assert "source tables: invoice_items, payments" in out
    assert 'field=config("table.include.list") op=exists' in out
    assert "field=db.host op==" in out


def test_search_service_live_dedupes_alias_scopes_and_preserves_metadata(
    tmp_path: Path, capsys
) -> None:
    _write_repo_manifests(tmp_path)
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    args = parser.parse_args(
        [
            "search",
            "--source",
            "live",
            "--env",
            "dev",
            "--cluster",
            "all",
            "--name",
            "dev.payments.payments_prod.source.postgres.0",
            "--output",
            "yaml",
        ]
    )
    rc = SearchService(ctx=ctx, logger=ctx.logger).run(args)
    assert rc == 0

    payload = yaml.safe_load(capsys.readouterr().out)
    assert payload["count"] == 1
    result = payload["results"][0]
    assert result["origin"] == "live"
    assert sorted(result["cluster"]) == ["acme-main", "acme-source"]
    assert len(result["alias_scopes"]) == 2
    assert sorted(ctx.connect_calls) == [("acme-external", "dev"), ("acme-main", "dev")]


def test_search_service_both_returns_separate_repo_and_live_hits(
    tmp_path: Path, capsys
) -> None:
    _write_repo_manifests(tmp_path)
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    args = parser.parse_args(
        [
            "search",
            "--source",
            "both",
            "--env",
            "dev",
            "--cluster",
            "all",
            "--name",
            "dev.payments.payments_prod.source.postgres.0",
            "--output",
            "json",
        ]
    )
    rc = SearchService(ctx=ctx, logger=ctx.logger).run(args)
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 2
    assert sorted(item["origin"] for item in payload["results"]) == ["live", "repo"]


def test_search_service_exact_live_name_skips_full_connector_list(
    tmp_path: Path, capsys
) -> None:
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    args = parser.parse_args(
        [
            "search",
            "--source",
            "live",
            "--env",
            "prod",
            "--cluster",
            "acme-external",
            "--name",
            "prod.acme.orders.sink.raw.iceberg.2",
            "--output",
            "json",
        ]
    )

    assert SearchService(ctx=ctx, logger=ctx.logger).run(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert ctx.connect_clients
    assert sum(client.list_calls for client in ctx.connect_clients) == 0
    assert ctx.connect_clients[0].config_calls == [
        "prod.acme.orders.sink.raw.iceberg.2"
    ]


def test_search_service_matches_full_sink_table_name_in_repo_and_live(
    tmp_path: Path, capsys
) -> None:
    _write_repo_manifests(tmp_path)
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    full_table_name = "dev__dbt__payments__payments_prod__raw.invoice_items__events"

    repo_args = parser.parse_args(
        [
            "search",
            "--source",
            "repo",
            "--env",
            "prod",
            "--table",
            "prod__dbt__payments__payments_prod__raw.invoice_items__events",
            "--output",
            "json",
        ]
    )
    rc = SearchService(ctx=ctx, logger=ctx.logger).run(repo_args)
    assert rc == 0
    repo_payload = json.loads(capsys.readouterr().out)
    assert repo_payload["count"] == 1
    assert repo_payload["results"][0]["name"] == (
        "prod.payments.payments_prod.sink.raw.iceberg.cdc.events.dbt.0"
    )
    assert any(
        item["field"] == "tables.sink_full"
        for item in repo_payload["results"][0]["matched"]
    )

    live_args = parser.parse_args(
        [
            "search",
            "--source",
            "live",
            "--env",
            "dev",
            "--cluster",
            "all",
            "--table",
            full_table_name,
            "--output",
            "json",
        ]
    )
    rc = SearchService(ctx=ctx, logger=ctx.logger).run(live_args)
    assert rc == 0
    live_payload = json.loads(capsys.readouterr().out)
    assert live_payload["count"] == 1
    assert live_payload["results"][0]["name"] == (
        "dev.payments.payments_prod.sink.raw.iceberg.cdc.events.dbt.0"
    )
    assert any(
        item["field"] == "tables.sink_full"
        for item in live_payload["results"][0]["matched"]
    )


def test_search_service_prompts_for_broad_live_defaults_and_logs_effective_values(
    tmp_path: Path, capsys, monkeypatch, caplog
) -> None:
    _write_repo_manifests(tmp_path)
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    monkeypatch.setattr(
        "connectctl.cli_helpers.default_scope_ux.is_interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(builtins, "input", lambda prompt: "n")

    args = parser.parse_args(
        [
            "search",
            "--source",
            "live",
            "--topic",
            "stage__cdc__users__acme_common__ods.acme_3__ma_users",
            "--output",
            "json",
        ]
    )

    with caplog.at_level(logging.INFO):
        rc = SearchService(ctx=ctx, logger=ctx.logger).run(args)

    assert rc == 1
    assert capsys.readouterr().out == ""
    assert "Effective selection for search" in caplog.text
    assert "env=all (implicit)" in caplog.text
    assert "cluster=all (implicit)" in caplog.text


def test_search_service_repo_matches_explicit_iceberg_tables_and_route_regex(
    tmp_path: Path, capsys
) -> None:
    _write_acme_orders_iceberg_route_manifest(tmp_path)
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    table_args = parser.parse_args(
        [
            "search",
            "--source",
            "repo",
            "--env",
            "prod",
            "--cluster",
            "acme-external",
            "--table",
            "prod__dbt__acme__orders__raw.exchange_rates__events",
            "--output",
            "json",
        ]
    )
    assert SearchService(ctx=ctx, logger=ctx.logger).run(table_args) == 0
    table_payload = json.loads(capsys.readouterr().out)
    assert table_payload["count"] == 1
    assert table_payload["results"][0]["name"] == "prod.acme.orders.sink.raw.iceberg.2"
    assert table_payload["results"][0]["tables"]["sink"] == [
        "daily_aggregated_exchange_rates__events",
        "exchange_rates__events",
    ]
    assert (
        "prod__dbt__acme__orders__raw.exchange_rates__events"
        in table_payload["results"][0]["tables"]["sink_full"]
    )
    assert any(
        item["field"] == "tables.sink_full"
        for item in table_payload["results"][0]["matched"]
    )
    assert table_payload["results"][0]["matched"][0]["sources"]
    assert any(
        item["field"] == "tables.sink_full"
        for item in table_payload["results"][0]["matched"][0]["occurrences"]
    )

    topic_args = parser.parse_args(
        [
            "search",
            "--source",
            "repo",
            "--env",
            "prod",
            "--cluster",
            "acme-external",
            "--topic",
            "acme.orders.exchange_rates",
            "--output",
            "json",
        ]
    )
    assert SearchService(ctx=ctx, logger=ctx.logger).run(topic_args) == 0
    topic_payload = json.loads(capsys.readouterr().out)
    assert topic_payload["count"] == 1
    assert topic_payload["results"][0]["topics"]["patterns"] == [
        "^acme\\.orders\\.daily_aggregated_exchange_rates$",
        "^acme\\.orders\\.exchange_rates$",
    ]
    assert any(
        item["field"] == "topics.pattern"
        for item in topic_payload["results"][0]["matched"]
    )


def test_search_service_repo_matches_iceberg_database_plus_short_table(
    tmp_path: Path, capsys
) -> None:
    _write_acme_orders_iceberg_route_manifest(tmp_path)
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    args = parser.parse_args(
        [
            "find",
            "--source",
            "repo",
            "--env",
            "prod",
            "--database",
            "prod__dbt__acme__orders__raw",
            "--table",
            "daily_aggregated_exchange_rates__events",
            "--output",
            "json",
        ]
    )

    assert SearchService(ctx=ctx, logger=ctx.logger).run(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["results"][0]["sink"]["database"] == ("prod__dbt__acme__orders__raw")
    assert sorted(item["field"] for item in payload["results"][0]["matched"]) == [
        "sink.database",
        "tables.sink",
    ]


def test_search_service_live_matches_explicit_iceberg_route_regex_by_topic_and_table(
    tmp_path: Path, capsys
) -> None:
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    args = parser.parse_args(
        [
            "search",
            "--source",
            "live",
            "--env",
            "prod",
            "--cluster",
            "acme-external",
            "--topic",
            "acme.orders.daily_aggregated_exchange_rates",
            "--table",
            "prod__dbt__acme__orders__raw.daily_aggregated_exchange_rates__events",
            "--output",
            "json",
        ]
    )

    assert SearchService(ctx=ctx, logger=ctx.logger).run(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    result = payload["results"][0]
    assert result["origin"] == "live"
    assert result["cluster"] == ["acme-external"]
    assert result["name"] == "prod.acme.orders.sink.raw.iceberg.2"
    assert ctx.connect_clients[0].config_calls == [
        "prod.acme.orders.sink.raw.iceberg.2"
    ]
    assert sorted(item["field"] for item in result["matched"]) == [
        "tables.sink_full",
        "topics.pattern",
    ]


def test_search_service_repo_matches_topic2table_map_without_topics_key(
    tmp_path: Path, capsys
) -> None:
    _write_repo_manifests(tmp_path)
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    args = parser.parse_args(
        [
            "search",
            "--source",
            "repo",
            "--env",
            "prod",
            "--cluster",
            "acme-external",
            "--system",
            "clickhouse",
            "--topic",
            "acme.events",
            "--table",
            "events_raw",
            "--output",
            "json",
        ]
    )

    assert SearchService(ctx=ctx, logger=ctx.logger).run(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    result = payload["results"][0]
    assert result["name"] == "prod.acme.events.sink.raw.clickhouse.0"
    assert result["topics"]["consumed"] == ["acme.events"]
    assert result["tables"]["sink"] == ["events_raw"]


def test_search_service_live_can_target_source_cluster_source_connectors(
    tmp_path: Path, capsys
) -> None:
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    args = parser.parse_args(
        [
            "search",
            "--source",
            "live",
            "--env",
            "prod",
            "--cluster",
            "acme-source",
            "--type",
            "source",
            "--database",
            "acme_common",
            "--table",
            "ma_balance",
            "--output",
            "json",
        ]
    )

    assert SearchService(ctx=ctx, logger=ctx.logger).run(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    result = payload["results"][0]
    assert result["name"] == "prod.user_finance.acme_common.source.mariadb.0"
    assert result["cluster"] == ["acme-source"]
    assert result["type"] == "source"
    table_match = next(
        item for item in result["matched"] if item["field"] == "tables.source"
    )
    assert table_match["sources"] == ['config("table.include.list")']


def test_search_service_explain_none_omits_sources_and_occurrences(
    tmp_path: Path, capsys
) -> None:
    _write_acme_orders_iceberg_route_manifest(tmp_path)
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    args = parser.parse_args(
        [
            "search",
            "--source",
            "repo",
            "--env",
            "prod",
            "--topic",
            "acme.orders.exchange_rates",
            "--explain",
            "none",
            "--output",
            "json",
        ]
    )

    assert SearchService(ctx=ctx, logger=ctx.logger).run(args) == 0
    payload = json.loads(capsys.readouterr().out)
    match = payload["results"][0]["matched"][0]
    assert "sources" not in match
    assert "occurrences" not in match


def test_search_service_explain_stats_includes_env_cluster_and_config_sources(
    tmp_path: Path, capsys
) -> None:
    _write_acme_orders_iceberg_route_manifest(tmp_path)
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    args = parser.parse_args(
        [
            "search",
            "--source",
            "repo",
            "--env",
            "prod",
            "--table",
            "prod__dbt__acme__orders__raw.exchange_rates__events",
            "--explain",
            "stats",
            "--output",
            "json",
        ]
    )

    assert SearchService(ctx=ctx, logger=ctx.logger).run(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stats"]["by_env_cluster"] == {"prod/acme-external": 1}
    assert payload["stats"]["by_field"] == {"tables.sink_full": 1}
    assert payload["stats"]["by_config_source"] == {
        'config("iceberg.table.prod__dbt__acme__orders__raw.exchange_rates__events.route-regex")': 1,
        'config("iceberg.tables")': 1,
    }
    assert "sources" not in payload["results"][0]["matched"][0]


def test_search_explain_option_is_not_confused_with_global_explain_flags() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "search",
            "--source",
            "repo",
            "--env",
            "prod",
            "--table",
            "orders",
            "--explain",
            "stats",
        ]
    )

    assert args.cmd == "search"
    assert args.explain == "stats"


def test_search_service_name_fuzzy_and_list_vars(tmp_path: Path, capsys) -> None:
    _write_acme_orders_iceberg_route_manifest(tmp_path)
    ctx = _build_ctx(tmp_path)
    parser = build_parser()

    fuzzy_args = parser.parse_args(
        [
            "search",
            "--source",
            "repo",
            "--env",
            "prod",
            "--name-fuzzy",
            "prod.acme.orders_exchnage.sink.raw.iceberg.2",
            "--output",
            "json",
        ]
    )

    assert SearchService(ctx=ctx, logger=ctx.logger).run(fuzzy_args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["results"][0]["matched"][0]["operator"] == "fuzzy"

    list_args = parser.parse_args(["search", "--list-vars"])
    assert SearchService(ctx=ctx, logger=ctx.logger).run(list_args) == 0
    out = capsys.readouterr().out
    assert "connector.name" in out
    assert 'config("key.with.dots")' in out
