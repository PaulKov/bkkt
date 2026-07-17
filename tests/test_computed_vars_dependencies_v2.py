from __future__ import annotations

import json
from pathlib import Path

import pytest

from connectctl import cli
from connectctl.exceptions import ConnectCtlError
from connectctl.rendering.factory import build_renderer
from connectctl.settings import Settings


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def _repo_args(tmp_path: Path) -> list[str]:
    return [
        "--repo-root",
        str(tmp_path),
        "--config",
        str(tmp_path / "connectctl.yaml"),
    ]


def _write_repo(tmp_path: Path, *, computed_body: str) -> Path:
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
      render:
        vars:
          server_id_namespace: prod-main
""",
        encoding="utf-8",
    )
    computed_path = tmp_path / "bkkt/computed_vars/custom.py"
    computed_path.parent.mkdir(parents=True, exist_ok=True)
    computed_path.write_text(computed_body, encoding="utf-8")

    manifest = (
        tmp_path
        / "connectors/demo/source/postgres/connector_demo__demo/prod.demo.demo.source.postgres.0.json"
    )
    _write_json(
        manifest,
        {
            "name": "prod.demo.demo.source.postgres.0",
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "topic.prefix": "${platform.topic_prefix}",
            },
        },
    )
    return manifest


def test_computed_var_dependency_chain_renders_and_reports_metadata(
    tmp_path: Path, capsys
) -> None:
    manifest = _write_repo(
        tmp_path,
        computed_body="""
from connectctl.plugins import ComputedVarContext, bkkt_computed_var

@bkkt_computed_var(name="platform.domain")
def domain(ctx: ComputedVarContext) -> str:
    return "prod.demo"

@bkkt_computed_var(name="platform.topic_prefix", depends_on=("platform.domain",))
def topic_prefix(ctx: ComputedVarContext) -> str:
    return "cdc." + str(ctx.variables.get("platform.domain")).replace(".", "-")
""",
    )
    settings = Settings.load(tmp_path / "connectctl.yaml", repo_root=tmp_path)

    rendered = build_renderer(settings).render(manifest)

    assert rendered.manifest.config["topic.prefix"] == "cdc.prod-demo"
    assert rendered.placeholder_context["platform.domain"] == "prod.demo"
    assert rendered.placeholder_sources["platform.domain"] == "computed:platform.domain"

    rc = cli.main(
        [*_repo_args(tmp_path), "vars", "computed", "list", "--output", "json"]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    by_name = {item["name"]: item for item in payload}
    assert by_name["platform.topic_prefix"]["dependencies"] == ["platform.domain"]

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "computed",
            "run",
            "platform.topic_prefix",
            "--manifest",
            str(manifest),
            "--output",
            "json",
        ]
    )
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["result"] == "cdc.prod-demo"

    contract = tmp_path / "bkkt/computed_vars/tests/dependencies.yaml"
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(
        f"""
cases:
  - name: topic prefix from dependent computed var
    variable: platform.topic_prefix
    manifest: "{manifest.relative_to(tmp_path).as_posix()}"
    expect: "cdc.prod-demo"
""",
        encoding="utf-8",
    )
    rc = cli.main(
        [*_repo_args(tmp_path), "vars", "computed", "test", "--output", "json"]
    )
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["summary"] == {
        "total": 1,
        "passed": 1,
        "failed": 0,
    }


def test_computed_var_missing_dependency_fails_before_render(tmp_path: Path) -> None:
    manifest = _write_repo(
        tmp_path,
        computed_body="""
from connectctl.plugins import ComputedVarContext, bkkt_computed_var

@bkkt_computed_var(name="platform.topic_prefix", depends_on=("platform.missing",))
def topic_prefix(ctx: ComputedVarContext) -> str:
    return "cdc." + str(ctx.variables.get("platform.missing"))
""",
    )
    settings = Settings.load(tmp_path / "connectctl.yaml", repo_root=tmp_path)

    with pytest.raises(ConnectCtlError, match="missing dependency"):
        build_renderer(settings).render(manifest)


def test_computed_var_cycle_fails_with_cycle_path(tmp_path: Path) -> None:
    manifest = _write_repo(
        tmp_path,
        computed_body="""
from connectctl.plugins import ComputedVarContext, bkkt_computed_var

@bkkt_computed_var(name="platform.a", depends_on=("platform.b",))
def a(ctx: ComputedVarContext) -> str:
    return str(ctx.variables.get("platform.b"))

@bkkt_computed_var(name="platform.b", depends_on=("platform.a",))
def b(ctx: ComputedVarContext) -> str:
    return str(ctx.variables.get("platform.a"))
""",
    )
    settings = Settings.load(tmp_path / "connectctl.yaml", repo_root=tmp_path)

    with pytest.raises(ConnectCtlError, match="cycle.*platform.a.*platform.b"):
        build_renderer(settings).render(manifest)


def test_vars_computed_graph_and_impact_cli(tmp_path: Path, capsys) -> None:
    _write_repo(
        tmp_path,
        computed_body="""
from connectctl.plugins import ComputedVarContext, bkkt_computed_var

@bkkt_computed_var(name="platform.domain")
def domain(ctx: ComputedVarContext) -> str:
    return "prod.demo"

@bkkt_computed_var(name="platform.topic_prefix", depends_on=("platform.domain",))
def topic_prefix(ctx: ComputedVarContext) -> str:
    return "cdc." + str(ctx.variables.get("platform.domain")).replace(".", "-")
""",
    )

    rc = cli.main(
        [*_repo_args(tmp_path), "vars", "computed", "graph", "--output", "json"]
    )
    assert rc == 0
    graph = json.loads(capsys.readouterr().out)
    assert {
        "id": "computed:platform.domain",
        "kind": "computed",
        "label": "platform.domain",
    } in graph["nodes"]
    assert {
        "from": "computed:platform.domain",
        "to": "computed:platform.topic_prefix",
        "kind": "depends_on",
    } in graph["edges"]

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "computed",
            "graph",
            "--format",
            "mermaid",
        ]
    )
    assert rc == 0
    mermaid = capsys.readouterr().out
    assert "graph TD" in mermaid
    assert "platform.domain" in mermaid

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "computed",
            "impact",
            "platform.domain",
            "--output",
            "json",
        ]
    )
    assert rc == 0
    impact = json.loads(capsys.readouterr().out)
    assert impact["query"] == "platform.domain"
    assert impact["computed_dependents"] == ["platform.topic_prefix"]
    assert impact["manifest_usages"][0]["config_key"] == "topic.prefix"
