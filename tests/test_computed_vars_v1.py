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


def _write_repo(
    tmp_path: Path,
    *,
    computed_body: str,
    manifest_vars: dict | None = None,
) -> Path:
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
    (tmp_path / "bkkt/computed_vars/custom.py").parent.mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / "bkkt/computed_vars/custom.py").write_text(
        computed_body,
        encoding="utf-8",
    )
    manifest = (
        tmp_path
        / "connectors/demo/source/postgres/connector_demo__demo/prod.demo.demo.source.postgres.0.json"
    )
    _write_json(
        manifest,
        {
            "name": "prod.demo.demo.source.postgres.0",
            "vars": manifest_vars
            or {
                "db": {"secret": "dbz-demo-prod"},
            },
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "topic.prefix": "${platform.topic_prefix}",
                "database.hostname": "${secretManager:${db.secret}:host}",
            },
        },
    )
    return manifest


def test_computed_var_renders_as_normal_placeholder_with_provenance(
    tmp_path: Path,
) -> None:
    manifest = _write_repo(
        tmp_path,
        computed_body="""
from connectctl.plugins import ComputedVarContext, bkkt_computed_var

@bkkt_computed_var(name="platform.topic_prefix", description="Topic prefix")
def topic_prefix(ctx: ComputedVarContext) -> str:
    assert ctx.variables.get("connector.name") == "prod.demo.demo.source.postgres.0"
    return "cdc." + str(ctx.variables.get("connector.name")).replace(".", "-")
""",
    )
    settings = Settings.load(tmp_path / "connectctl.yaml", repo_root=tmp_path)

    rendered = build_renderer(settings).render(manifest)

    assert (
        rendered.manifest.config["topic.prefix"]
        == "cdc.prod-demo-demo-source-postgres-0"
    )
    assert rendered.placeholder_context["platform.topic_prefix"] == (
        "cdc.prod-demo-demo-source-postgres-0"
    )
    assert (
        rendered.placeholder_sources["platform.topic_prefix"]
        == "computed:platform.topic_prefix"
    )


def test_computed_var_cannot_shadow_existing_repo_var_without_explicit_allow(
    tmp_path: Path,
) -> None:
    manifest = _write_repo(
        tmp_path,
        manifest_vars={"platform": {"topic_prefix": "repo-value"}},
        computed_body="""
from connectctl.plugins import ComputedVarContext, bkkt_computed_var

@bkkt_computed_var(name="platform.topic_prefix")
def topic_prefix(ctx: ComputedVarContext) -> str:
    return "computed-value"
""",
    )
    settings = Settings.load(tmp_path / "connectctl.yaml", repo_root=tmp_path)

    with pytest.raises(ConnectCtlError, match="shadows existing variable"):
        build_renderer(settings).render(manifest)


def test_computed_var_can_shadow_existing_repo_var_when_declared(
    tmp_path: Path,
) -> None:
    manifest = _write_repo(
        tmp_path,
        manifest_vars={"platform": {"topic_prefix": "repo-value"}},
        computed_body="""
from connectctl.plugins import ComputedVarContext, bkkt_computed_var

@bkkt_computed_var(name="platform.topic_prefix", allow_shadow=True)
def topic_prefix(ctx: ComputedVarContext) -> str:
    return "computed-value"
""",
    )
    settings = Settings.load(tmp_path / "connectctl.yaml", repo_root=tmp_path)

    rendered = build_renderer(settings).render(manifest)

    assert rendered.manifest.config["topic.prefix"] == "computed-value"
    assert (
        rendered.placeholder_sources["platform.topic_prefix"]
        == "computed:platform.topic_prefix"
    )


def test_computed_var_rejects_non_scalar_output(tmp_path: Path) -> None:
    manifest = _write_repo(
        tmp_path,
        computed_body="""
from connectctl.plugins import ComputedVarContext, bkkt_computed_var

@bkkt_computed_var(name="platform.topic_prefix")
def topic_prefix(ctx: ComputedVarContext) -> dict:
    return {"bad": True}
""",
    )
    settings = Settings.load(tmp_path / "connectctl.yaml", repo_root=tmp_path)

    with pytest.raises(ConnectCtlError, match="must return scalar"):
        build_renderer(settings).render(manifest)


def test_vars_computed_cli_and_contract_tests(tmp_path: Path, capsys) -> None:
    manifest = _write_repo(
        tmp_path,
        computed_body="""
from connectctl.plugins import ComputedVarContext, bkkt_computed_var

@bkkt_computed_var(name="platform.topic_prefix", description="Topic prefix")
def topic_prefix(ctx: ComputedVarContext) -> str:
    return "cdc." + str(ctx.variables.get("connector.name")).replace(".", "-")
""",
    )
    tests_file = tmp_path / "bkkt/computed_vars/tests/topic_prefix.yaml"
    tests_file.parent.mkdir(parents=True, exist_ok=True)
    tests_file.write_text(
        f"""
cases:
  - name: topic prefix from manifest context
    variable: platform.topic_prefix
    manifest: "{manifest.relative_to(tmp_path).as_posix()}"
    expect: "cdc.prod-demo-demo-source-postgres-0"
""",
        encoding="utf-8",
    )

    rc = cli.main(
        [*_repo_args(tmp_path), "vars", "computed", "list", "--output", "json"]
    )
    assert rc == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed[0]["name"] == "platform.topic_prefix"
    assert listed[0]["source"] == "repo"

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
    run_payload = json.loads(capsys.readouterr().out)
    assert run_payload["result"] == "cdc.prod-demo-demo-source-postgres-0"
    assert run_payload["variable"]["name"] == "platform.topic_prefix"

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "computed",
            "explain",
            "platform.topic_prefix",
            "--output",
            "json",
        ]
    )
    assert rc == 0
    explain_payload = json.loads(capsys.readouterr().out)
    assert explain_payload["name"] == "platform.topic_prefix"
    assert explain_payload["description"] == "Topic prefix"

    rc = cli.main(
        [*_repo_args(tmp_path), "vars", "computed", "doctor", "--output", "json"]
    )
    assert rc == 0
    doctor_payload = json.loads(capsys.readouterr().out)
    assert doctor_payload["status"] == "ok"
    assert doctor_payload["computed_vars"][0]["name"] == "platform.topic_prefix"

    rc = cli.main(
        [*_repo_args(tmp_path), "vars", "computed", "test", "--output", "json"]
    )
    assert rc == 0
    test_payload = json.loads(capsys.readouterr().out)
    assert test_payload["status"] == "ok"
    assert test_payload["summary"] == {"total": 1, "passed": 1, "failed": 0}
