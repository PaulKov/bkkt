from __future__ import annotations

import json
from pathlib import Path

from connectctl import cli


def _repo_args(tmp_path: Path) -> list[str]:
    return [
        "--repo-root",
        str(tmp_path),
        "--config",
        str(tmp_path / "connectctl.yaml"),
    ]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_repo(tmp_path: Path) -> Path:
    (tmp_path / "connectctl.yaml").write_text(
        """
connectors_root: connectors
default_cluster: acme-main
clusters:
  acme-main:
    prod:
      connect:
        scheme: http
        port: 8083
        hosts: ["127.0.0.1"]
""",
        encoding="utf-8",
    )
    manifest = (
        tmp_path
        / "connectors/demo/source/postgres/connector_demo__demo/prod.demo.demo.source.postgres.0.json"
    )
    base = manifest.with_name("base.demo.demo.source.postgres.0.json")
    _write_json(
        base,
        {
            "name": "prod.demo.demo.source.postgres.0",
            "vars": {"domain": "demo"},
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "${secretManager:${db.secret}:host}",
                "topic.prefix": "${platform.topic_prefix}",
                "route.field": "${fn:platform.slug(platform.topic_prefix)}",
            },
        },
    )
    _write_json(
        manifest,
        {
            "config": {
                "slot.name": "slot_${platform.topic_prefix}",
            },
        },
    )
    _write_provider(tmp_path)
    _write_computed_var(tmp_path)
    _write_function(tmp_path)
    return manifest


def _write_provider(tmp_path: Path) -> None:
    provider = tmp_path / "bkkt/var_providers/platform.py"
    provider.parent.mkdir(parents=True, exist_ok=True)
    provider.write_text(
        """
from connectctl.plugins import VarProviderContext, bkkt_var_provider

@bkkt_var_provider(name="platform.db", provides=("db.secret",))
def provide_db(*, ctx: VarProviderContext) -> dict[str, str]:
    return {"db.secret": "dbz-" + str(ctx.variables.get("domain"))}
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_computed_var(tmp_path: Path) -> None:
    computed = tmp_path / "bkkt/computed_vars/platform.py"
    computed.parent.mkdir(parents=True, exist_ok=True)
    computed.write_text(
        """
from connectctl.plugins import ComputedVarContext, bkkt_computed_var

@bkkt_computed_var(name="platform.topic_prefix", depends_on=("db.secret",))
def topic_prefix(*, ctx: ComputedVarContext) -> str:
    return "cdc." + str(ctx.variables.get("db.secret")).replace("_", "-")
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_function(tmp_path: Path) -> None:
    function = tmp_path / "bkkt/functions/platform.py"
    function.parent.mkdir(parents=True, exist_ok=True)
    function.write_text(
        """
from connectctl.plugins import bkkt_function

@bkkt_function(name="platform.slug")
def slug(value: str) -> str:
    return value.replace(".", "_")
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _edge_set(payload: dict) -> set[tuple[str, str, str]]:
    return {(item["from"], item["kind"], item["to"]) for item in payload["edges"]}


def _node_kinds(payload: dict) -> dict[str, str]:
    return {item["id"]: item["kind"] for item in payload["nodes"]}


def test_vars_graph_shows_provider_computed_function_and_inherited_config(
    tmp_path: Path, capsys
) -> None:
    manifest = _write_repo(tmp_path)

    rc = cli.main(
        [*_repo_args(tmp_path), "vars", "graph", str(manifest), "--output", "json"]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    node_kinds = _node_kinds(payload)
    edges = _edge_set(payload)
    assert node_kinds["provider:platform.db"] == "provider"
    assert node_kinds["computed:platform.topic_prefix"] == "computed"
    assert node_kinds["fn:platform.slug"] == "function"
    assert node_kinds["config:database.hostname"] == "config"
    assert (
        "provider:platform.db",
        "provides",
        "var:db.secret",
    ) in edges
    assert (
        "var:db.secret",
        "depends_on",
        "computed:platform.topic_prefix",
    ) in edges
    assert (
        "computed:platform.topic_prefix",
        "provides",
        "var:platform.topic_prefix",
    ) in edges
    assert (
        "var:platform.topic_prefix",
        "fn_arg",
        "fn:platform.slug",
    ) in edges
    assert (
        "fn:platform.slug",
        "renders",
        "config:route.field",
    ) in edges
    assert (
        "var:platform.topic_prefix",
        "placeholder",
        "config:slot.name",
    ) in edges


def test_vars_trace_shows_computed_source_and_provider_dependency(
    tmp_path: Path, capsys
) -> None:
    manifest = _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "trace",
            str(manifest),
            "platform.topic_prefix",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["source"] == "computed:platform.topic_prefix"
    steps = {(item["kind"], item["name"], item["source"]) for item in payload["steps"]}
    assert (
        "computed",
        "platform.topic_prefix",
        "computed:platform.topic_prefix",
    ) in steps
    assert ("variable", "db.secret", "provider:platform.db") in steps
    assert ("provider", "platform.db", "provider:platform.db") in steps
    usages = {
        (item["config_key"], item["kind"], item["via_function"])
        for item in payload["usages"]
    }
    assert ("topic.prefix", "placeholder", None) in usages
    assert ("slot.name", "placeholder", None) in usages
    assert ("route.field", "fn_arg", "platform.slug") in usages


def test_render_trace_uses_effective_template_and_shows_full_chain(
    tmp_path: Path, capsys
) -> None:
    manifest = _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "render",
            "trace",
            str(manifest),
            "--config-key",
            "route.field",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["final_value"] == "cdc_dbz-demo"
    steps = {(item["kind"], item["name"], item["source"]) for item in payload["steps"]}
    assert ("function", "platform.slug", None) in steps
    assert (
        "variable",
        "platform.topic_prefix",
        "computed:platform.topic_prefix",
    ) in steps
    assert (
        "computed",
        "platform.topic_prefix",
        "computed:platform.topic_prefix",
    ) in steps
    assert ("variable", "db.secret", "provider:platform.db") in steps
    assert ("provider", "platform.db", "provider:platform.db") in steps
