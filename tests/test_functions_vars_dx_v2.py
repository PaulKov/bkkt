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
    functions_file = tmp_path / "bkkt/functions/platform.py"
    functions_file.parent.mkdir(parents=True, exist_ok=True)
    functions_file.write_text(
        """
from connectctl.plugins import FunctionContext, bkkt_function

@bkkt_function(name="platform.slug", description="Normalize values")
def slug(value: str, *, max_len: int = 63, ctx: FunctionContext) -> str:
    return str(value).lower().replace(".", "-")[:max_len]
""",
        encoding="utf-8",
    )
    contract_file = tmp_path / "bkkt/functions/tests/platform.slug.yaml"
    contract_file.parent.mkdir(parents=True, exist_ok=True)
    contract_file.write_text(
        """
cases:
  - name: platform.slug lowercases and trims
    function: platform.slug
    args: ["MY.VALUE"]
    kwargs:
      max_len: 4
    expect: "my-v"
""",
        encoding="utf-8",
    )
    schema_file = tmp_path / "bkkt/vars.schema.yaml"
    schema_file.parent.mkdir(parents=True, exist_ok=True)
    schema_file.write_text(
        """
version: 1
vars:
  db.secret:
    type: string
    required: true
    sensitive: true
    description: Database secret name
""",
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
            "vars": {"db": {"secret": "dbz-demo-prod"}},
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "${secretManager:${db.secret}:host}",
                "topic.prefix": "cdc.${fn:platform.slug(connector.name, max_len=24)}",
            },
        },
    )
    return manifest


def test_functions_scaffold_with_fixture_dry_run_and_write(
    tmp_path: Path, capsys, caplog
) -> None:
    _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "scaffold",
            "platform.new_slug",
            "--with-fixture",
            "--path",
            "bkkt/functions/new_slug.py",
            "--dry-run",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "function_scaffold"
    assert payload["status"] == "planned"
    assert [item["kind"] for item in payload["files"]] == [
        "function",
        "function_contract",
        "render_fixture",
        "template_test",
    ]
    function_file = payload["files"][0]
    assert function_file["path"] == "bkkt/functions/new_slug.py"
    assert '@bkkt_function(name="platform.new_slug"' in function_file["content"]
    assert "def new_slug(" in function_file["content"]
    assert "def platform.new_slug" not in function_file["content"]

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "scaffold",
            "platform.new_slug",
            "--with-fixture",
            "--path",
            "bkkt/functions/new_slug.py",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    created = json.loads(capsys.readouterr().out)
    assert created["status"] == "created"
    assert (tmp_path / "bkkt/functions/new_slug.py").exists()
    assert (tmp_path / "bkkt/functions/tests/platform.new_slug.yaml").exists()
    assert (tmp_path / "bkkt/templates/fixtures/platform.new_slug.json").exists()
    assert (tmp_path / "bkkt/templates/tests/platform.new_slug.yaml").exists()

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "scaffold",
            "platform.new_slug",
            "--with-fixture",
            "--path",
            "bkkt/functions/new_slug.py",
            "--output",
            "json",
        ]
    )
    assert rc == 2
    assert "already exists" in caplog.text


def test_functions_review_combines_contracts_and_impact(tmp_path: Path, capsys) -> None:
    manifest = _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "review",
            "platform.slug",
            "--with-render-diff",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "function_review"
    assert payload["status"] == "ok"
    assert payload["function"]["name"] == "platform.slug"
    assert payload["impact"]["summary"]["matches"] == 1
    assert (
        payload["impact"]["matches"][0]["manifest"]
        == manifest.relative_to(tmp_path).as_posix()
    )
    assert payload["contracts"]["status"] == "ok"
    assert payload["contracts"]["summary"]["total"] == 1
    checklist = {item["code"]: item["status"] for item in payload["checklist"]}
    assert checklist["function_registered"] == "ok"
    assert checklist["contract_tests"] == "ok"
    assert checklist["usage_impact"] == "ok"


def test_vars_review_reports_schema_sensitivity_and_render_diff(
    tmp_path: Path, capsys
) -> None:
    manifest = _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "review",
            "db.secret",
            "--with-render-diff",
            "--set",
            "db.secret=dbz-demo-next",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "variable_review"
    assert payload["status"] == "ok"
    assert payload["schema"]["key"] == "db.secret"
    assert payload["schema"]["sensitive"] is True
    assert payload["impact"]["summary"]["matches"] == 1
    assert (
        payload["impact"]["matches"][0]["manifest"]
        == manifest.relative_to(tmp_path).as_posix()
    )
    assert payload["impact"]["render_diffs"] == [
        {
            "manifest": manifest.relative_to(tmp_path).as_posix(),
            "config_key": "database.hostname",
            "before": "${secretManager:dbz-demo-prod:host}",
            "after": "${secretManager:dbz-demo-next:host}",
        }
    ]
    checklist = {item["code"]: item["status"] for item in payload["checklist"]}
    assert checklist["schema_entry"] == "ok"
    assert checklist["usage_impact"] == "ok"
    assert checklist["render_diff"] == "ok"
