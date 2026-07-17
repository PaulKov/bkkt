from __future__ import annotations

from types import SimpleNamespace

from connectctl.cli_parser import build_parser
from connectctl.models import (
    ConnectorManifest,
    ConnectorPathInfo,
    ConnectorType,
    Environment,
)
from connectctl.services.apply.artifacts import write_rollback_artifact
from connectctl.services.operator.discovery import DiscoveryOptions, DiscoveryService
from connectctl.services.operator.lineage import build_lineage_graph, render_mermaid
from connectctl.services.operator.runbooks import RunbookRouter

from test_search_service import _build_ctx, _write_repo_manifests


def _args(**overrides):
    defaults = {
        "source": "repo",
        "env": "all",
        "cluster": "all",
        "ignore_case": False,
        "limit": 50,
        "kind": "auto",
        "jobs": 8,
        "rate_limit_per_second": 0,
        "burst": None,
        "vars": None,
        "vars_file": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_cli_parser_exposes_kept_operator_commands() -> None:
    parser = build_parser()

    assert (
        parser.parse_args(
            ["lineage", "prod.demo.source.postgres.0", "--output", "mermaid"]
        ).output
        == "mermaid"
    )
    assert (
        parser.parse_args(["reconcile", "--env", "prod", "--names", "a.b"]).cmd
        == "reconcile"
    )


def test_apply_accepts_operator_safety_aliases() -> None:
    parser = build_parser()

    apply_args = parser.parse_args(
        [
            "apply",
            "--env",
            "prod",
            "--health-gates",
            "--post-smoke",
            "--wait-timeout-seconds",
            "42",
            "connectors/demo/prod.json",
        ]
    )
    assert apply_args.health_gates is True
    assert apply_args.smoke is True
    assert apply_args.timeout_seconds == 42


def test_apply_keeps_timeout_default_without_alias() -> None:
    """Dry-run UX must not require an explicit timeout workaround."""

    parser = build_parser()

    apply_args = parser.parse_args(
        [
            "apply",
            "--env",
            "prod",
            "--dry-run",
            "connectors/demo/prod.json",
        ]
    )
    assert apply_args.timeout_seconds == 300


def test_discovery_resolves_live_iceberg_full_table(tmp_path) -> None:
    ctx = _build_ctx(tmp_path)
    args = _args(source="live", env="prod", cluster="acme-external")
    options = DiscoveryOptions.from_args(args)

    result = DiscoveryService(ctx=ctx).resolve(
        "prod__dbt__acme__orders__raw.exchange_rates__events",
        options=options,
        args=args,
    )

    assert [item.facts.name for item in result.results] == [
        "prod.acme.orders.sink.raw.iceberg.2"
    ]
    assert result.results[0].matched[0].field in {
        "tables.sink_full",
        "tables.sink",
    }
    assert ctx.connect_clients[0].config_calls == [
        "prod.acme.orders.sink.raw.iceberg.2"
    ]


def test_discovery_exact_live_connector_uses_direct_config_fetch(tmp_path) -> None:
    ctx = _build_ctx(tmp_path)
    args = _args(source="live", env="prod", cluster="all")
    options = DiscoveryOptions.from_args(args)

    result = DiscoveryService(ctx=ctx).resolve(
        "prod.acme.orders.sink.raw.iceberg.2",
        options=options,
        args=args,
    )

    assert [item.facts.name for item in result.results] == [
        "prod.acme.orders.sink.raw.iceberg.2"
    ]
    assert ctx.connect_clients
    assert sum(client.list_calls for client in ctx.connect_clients) == 0


def test_lineage_graph_links_source_topic_sink_table(tmp_path) -> None:
    _write_repo_manifests(tmp_path)
    ctx = _build_ctx(tmp_path)
    args = _args(
        source="repo",
        env="prod",
        cluster="acme-main",
        object="payments",
    )
    options = DiscoveryOptions.from_args(args)
    discovery = DiscoveryService(ctx=ctx).resolve(
        "payments", options=options, args=args
    )
    nodes, edges = build_lineage_graph(tuple(item.facts for item in discovery.results))

    assert any(node.kind == "connector" for node in nodes)
    assert any(edge.label in {"produces", "writes", "captures"} for edge in edges)
    assert "flowchart LR" in render_mermaid(nodes, edges)


def test_runbook_router_suggests_search_for_empty_discovery(tmp_path) -> None:
    ctx = _build_ctx(tmp_path)
    args = _args(source="repo", env="prod", cluster="acme-main")
    options = DiscoveryOptions.from_args(args)
    discovery = DiscoveryService(ctx=ctx).resolve(
        "missing-object", options=options, args=args
    )

    suggestions = RunbookRouter.default().suggest_for_discovery(discovery)

    assert any(item.id == "search" for item in suggestions)


def test_rollback_artifact_contains_exact_previous_and_desired_config(tmp_path) -> None:
    manifest_path = tmp_path / "connectors/demo/prod.json"
    manifest_path.parent.mkdir(parents=True)
    info = ConnectorPathInfo(
        path=manifest_path,
        relpath=manifest_path.relative_to(tmp_path),
        domain="demo",
        connector_type=ConnectorType.sink,
        system="iceberg",
        connector_dir="connector_demo__orders",
        env=Environment.prod,
        remainder="demo.orders.sink.raw.iceberg.0",
    )
    manifest = ConnectorManifest(
        name="prod.demo.orders.sink.raw.iceberg.0",
        config={"tasks.max": "2", "topics": "orders.v2"},
        source_path=manifest_path,
        info=info,
    )

    out = write_rollback_artifact(
        tmp_path / "rendered" / "prod",
        manifest,
        previous_config={"tasks.max": "1", "topics": "orders"},
        desired_config=manifest.config,
        error=RuntimeError("post-smoke failed"),
    )

    text = out.read_text(encoding="utf-8")
    assert "orders.v2" in text
    assert "post-smoke failed" in text
    assert '"previous_config"' in text
