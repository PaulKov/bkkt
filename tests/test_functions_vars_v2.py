from __future__ import annotations

import json
from pathlib import Path

from connectctl import cli


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def _write_base_repo(tmp_path: Path, *, function_body: str | None = None) -> Path:
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
    if function_body is not None:
        function_file = tmp_path / "bkkt/functions/custom.py"
        function_file.parent.mkdir(parents=True, exist_ok=True)
        function_file.write_text(function_body, encoding="utf-8")

    manifest = (
        tmp_path
        / "connectors/demo/source/postgres/connector_demo__demo/prod.demo.demo.source.postgres.0.json"
    )
    _write_json(
        manifest,
        {
            "name": "prod.demo.demo.source.postgres.0",
            "vars": {
                "db": {"secret": "dbz-demo-prod"},
                "retry": {"max": 34},
                "old": {"name": "legacy"},
            },
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "${secretManager:${db.secret}:host}",
                "topic.prefix": "cdc.${fn:slug(connector.name, max_len=24)}",
                "routing.cluster": "${target.cluster.name}",
            },
        },
    )
    return manifest


def _repo_args(tmp_path: Path) -> list[str]:
    return [
        "--repo-root",
        str(tmp_path),
        "--config",
        str(tmp_path / "connectctl.yaml"),
    ]


def test_vars_doctor_validates_typed_schema(tmp_path: Path, capsys) -> None:
    manifest = _write_base_repo(
        tmp_path,
        function_body="""
from connectctl.plugins import bkkt_function

@bkkt_function(name="slug")
def slug(value: str, *, max_len: int = 63) -> str:
    return str(value).replace(".", "-")[:max_len]
""",
    )
    (tmp_path / "bkkt/vars.schema.yaml").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "bkkt/vars.schema.yaml").write_text(
        """
version: 1
vars:
  db.secret:
    type: string
    required: true
    pattern: "^dbz-"
  retry.max:
    type: int
    required: true
  env:
    type: string
    enum: ["prod"]
  old.name:
    type: string
    deprecated: true
  missing.required:
    type: string
    required: true
""",
        encoding="utf-8",
    )

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "doctor",
            str(manifest),
            "--output",
            "json",
        ]
    )

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["schema_path"].endswith("bkkt/vars.schema.yaml")
    assert {issue["code"] for issue in payload["issues"]} == {
        "required_missing",
        "deprecated",
    }
    assert any(issue["key"] == "missing.required" for issue in payload["issues"])
    assert any(issue["key"] == "old.name" for issue in payload["issues"])


def test_vars_doctor_passes_when_schema_matches(tmp_path: Path, capsys) -> None:
    manifest = _write_base_repo(
        tmp_path,
        function_body="""
from connectctl.plugins import bkkt_function

@bkkt_function(name="slug")
def slug(value: str, *, max_len: int = 63) -> str:
    return str(value).replace(".", "-")[:max_len]
""",
    )
    (tmp_path / "bkkt/vars.schema.yaml").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "bkkt/vars.schema.yaml").write_text(
        """
version: 1
vars:
  db.secret:
    type: string
    required: true
    pattern: "^dbz-"
  retry.max:
    type: int
    required: true
  env:
    type: string
    enum: ["prod"]
""",
        encoding="utf-8",
    )

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "doctor",
            str(manifest),
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["issues"] == []


def test_vars_doctor_reports_type_enum_and_pattern_mismatch(
    tmp_path: Path, capsys
) -> None:
    manifest = _write_base_repo(
        tmp_path,
        function_body="""
from connectctl.plugins import bkkt_function

@bkkt_function(name="slug")
def slug(value: str, *, max_len: int = 63) -> str:
    return str(value)[:max_len]
""",
    )
    (tmp_path / "bkkt/vars.schema.yaml").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "bkkt/vars.schema.yaml").write_text(
        """
version: 1
vars:
  db.secret:
    type: string
    pattern: "^vault-"
  retry.max:
    type: string
  env:
    type: string
    enum: ["stage"]
""",
        encoding="utf-8",
    )

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "doctor",
            str(manifest),
            "--output",
            "json",
        ]
    )

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert {issue["code"] for issue in payload["issues"]} == {
        "enum_mismatch",
        "pattern_mismatch",
        "type_mismatch",
    }


def test_functions_test_runs_yaml_contract_cases(tmp_path: Path, capsys) -> None:
    manifest = _write_base_repo(
        tmp_path,
        function_body="""
from connectctl.plugins import bkkt_function

@bkkt_function(name="slug", description="Normalize connector fragments")
def slug(value: str, *, max_len: int = 63) -> str:
    return str(value).lower().replace("_", "-")[:max_len]
""",
    )
    tests_file = tmp_path / "bkkt/functions/tests/slug.yaml"
    tests_file.parent.mkdir(parents=True, exist_ok=True)
    tests_file.write_text(
        f"""
cases:
  - name: lowercases and trims
    function: slug
    args: ["MY_VALUE"]
    kwargs:
      max_len: 4
    expect: "my-v"
  - name: reports mismatch with context
    function: slug
    args: ["Bad_Value"]
    kwargs:
      max_len: 99
    manifest: "{manifest.relative_to(tmp_path).as_posix()}"
    expect: "different"
""",
        encoding="utf-8",
    )

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "test",
            "--output",
            "json",
        ]
    )

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["summary"] == {"total": 2, "passed": 1, "failed": 1}
    failed = [case for case in payload["cases"] if case["status"] == "failed"]
    assert failed[0]["name"] == "reports mismatch with context"
    assert failed[0]["expected"] == "different"
    assert failed[0]["actual"] == "bad-value"


def test_functions_test_passes_with_no_contract_files(tmp_path: Path, capsys) -> None:
    _write_base_repo(
        tmp_path,
        function_body="""
from connectctl.plugins import bkkt_function

@bkkt_function(name="slug")
def slug(value: str) -> str:
    return str(value)
""",
    )

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "test",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["summary"] == {"total": 0, "passed": 0, "failed": 0}


def test_functions_run_contract_check_blocks_bad_args(tmp_path: Path, capsys) -> None:
    _write_base_repo(
        tmp_path,
        function_body="""
from connectctl.plugins import bkkt_function

@bkkt_function(name="slug")
def slug(value: str, *, max_len: int = 63) -> str:
    return str(value).replace(".", "-")[:max_len]
""",
    )

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "run",
            "slug",
            "--arg",
            "demo.name",
            "--kw",
            'max_len="bad"',
            "--contract-check",
            "--output",
            "json",
        ]
    )

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["function"]["name"] == "slug"
    assert payload["contract"]["status"] == "failed"
    assert payload["contract_issues"][0]["code"] == "function_arg_type_mismatch"
    assert payload["contract_issues"][0]["parameter"] == "max_len"
    assert payload["contract_issues"][0]["expected"] == "int"
    assert payload["contract_issues"][0]["actual_type"] == "str"
    assert "result" not in payload


def test_functions_run_contract_check_reports_ok_contract(
    tmp_path: Path, capsys
) -> None:
    _write_base_repo(
        tmp_path,
        function_body="""
from connectctl.plugins import bkkt_function

@bkkt_function(name="slug")
def slug(value: str, *, max_len: int = 63) -> str:
    return str(value).replace(".", "-")[:max_len]
""",
    )

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "run",
            "slug",
            "--arg",
            "demo.name",
            "--kw",
            "max_len=4",
            "--contract-check",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["contract"] == {"status": "ok", "issues": []}
    assert payload["result"] == "demo"


def test_functions_doctor_strict_reports_risky_repo_function_code(
    tmp_path: Path, capsys
) -> None:
    _write_base_repo(
        tmp_path,
        function_body="""
import random
import requests
from connectctl.plugins import bkkt_function

@bkkt_function(name="slug")
def slug(value: str) -> str:
    open("/tmp/leak", "w").write(str(random.random()))
    requests.get("https://example.com")
    return str(value)
""",
    )

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "doctor",
            "--strict",
            "--output",
            "json",
        ]
    )

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert {issue["code"] for issue in payload["strict_issues"]} >= {
        "risky_import",
        "risky_call",
    }
    assert all(
        issue["file"].endswith("bkkt/functions/custom.py")
        for issue in payload["strict_issues"]
    )


def test_vars_graph_reports_variable_and_function_dependencies(
    tmp_path: Path, capsys
) -> None:
    manifest = _write_base_repo(
        tmp_path,
        function_body="""
from connectctl.plugins import bkkt_function

@bkkt_function(name="slug")
def slug(value: str, *, max_len: int = 63) -> str:
    return str(value).lower().replace(".", "-")[:max_len]
""",
    )

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "graph",
            str(manifest),
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    node_ids = {node["id"] for node in payload["nodes"]}
    assert "var:db.secret" in node_ids
    assert "var:connector.name" in node_ids
    assert "fn:slug" in node_ids
    assert "config:topic.prefix" in node_ids
    edges = {(edge["from"], edge["to"], edge["kind"]) for edge in payload["edges"]}
    assert ("var:connector.name", "fn:slug", "fn_arg") in edges
    assert ("fn:slug", "config:topic.prefix", "renders") in edges
    assert ("var:db.secret", "config:database.hostname", "placeholder") in edges

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "graph",
            str(manifest),
            "--format",
            "mermaid",
        ]
    )

    assert rc == 0
    mermaid = capsys.readouterr().out
    assert mermaid.startswith("graph TD")
    assert "fn_slug" in mermaid
