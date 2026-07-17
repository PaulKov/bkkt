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

@bkkt_function(name="platform.uncovered", description="No contracts yet")
def uncovered(value: str, *, ctx: FunctionContext) -> str:
    return str(value)

@bkkt_function(
    name="platform.expired",
    description="Expired helper",
    deprecated_since="2025-01-01",
    remove_after="2026-01-01",
    replacement="platform.slug",
)
def expired(value: str, *, ctx: FunctionContext) -> str:
    return str(value)
""",
        encoding="utf-8",
    )
    (tmp_path / "bkkt/functions/tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "bkkt/functions/tests/platform.slug.yaml").write_text(
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
    (tmp_path / "bkkt/vars.schema.yaml").write_text(
        """
version: 1
vars:
  db.secret:
    type: string
    required: true
    sensitive: true
    description: Database secret name
  old.topic.prefix:
    type: string
    deprecated: true
    replacement: topic.prefix
    remove_after: "2026-09-01"
  expired.topic.prefix:
    type: string
    deprecated: true
    replacement: topic.prefix
    remove_after: "2026-01-01"
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
            "vars": {
                "db": {"secret": "dbz-demo-prod"},
                "old": {"topic": {"prefix": "legacy-topic"}},
            },
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "${secretManager:${db.secret}:host}",
                "topic.prefix": "cdc.${fn:platform.slug(connector.name, max_len=24)}",
                "legacy.topic": "${old.topic.prefix}",
                "expired.topic": "${expired.topic.prefix}",
                "undocumented.topic": "${undocumented.topic.prefix}",
                "expired.fn.topic": "${fn:platform.expired(connector.name)}",
            },
        },
    )
    return manifest


def test_functions_and_vars_coverage_reports_gaps(tmp_path: Path, capsys) -> None:
    _write_repo(tmp_path)

    rc = cli.main([*_repo_args(tmp_path), "functions", "coverage", "--output", "json"])

    assert rc == 0
    functions_payload = json.loads(capsys.readouterr().out)
    assert functions_payload["kind"] == "function_coverage"
    items = {item["name"]: item for item in functions_payload["items"]}
    assert items["platform.slug"]["usage_count"] == 1
    assert items["platform.slug"]["contract_tests"]["status"] == "ok"
    assert items["platform.uncovered"]["contract_tests"]["status"] == "missing"
    assert items["platform.uncovered"]["status"] == "warning"

    rc = cli.main([*_repo_args(tmp_path), "vars", "coverage", "--output", "json"])

    assert rc == 0
    vars_payload = json.loads(capsys.readouterr().out)
    assert vars_payload["kind"] == "variable_coverage"
    vars_items = {item["key"]: item for item in vars_payload["items"]}
    assert vars_items["db.secret"]["schema_entry"]["status"] == "ok"
    assert vars_items["db.secret"]["schema_entry"]["sensitive"] is True
    assert vars_items["old.topic.prefix"]["schema_entry"]["deprecated"] is True
    assert (
        vars_items["undocumented.topic.prefix"]["schema_entry"]["status"] == "missing"
    )
    assert vars_payload["summary"]["schema_entries"] == 3


def test_strict_coverage_fails_on_missing_contracts_and_schema(
    tmp_path: Path, capsys
) -> None:
    _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "coverage",
            "--strict",
            "--output",
            "json",
        ]
    )

    assert rc == 1
    functions_payload = json.loads(capsys.readouterr().out)
    assert functions_payload["status"] == "failed"
    function_issues = {issue["code"] for issue in functions_payload["issues"]}
    assert "missing_function_contract" in function_issues

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "coverage",
            "--strict",
            "--output",
            "json",
        ]
    )

    assert rc == 1
    vars_payload = json.loads(capsys.readouterr().out)
    assert vars_payload["status"] == "failed"
    var_issues = {issue["code"] for issue in vars_payload["issues"]}
    assert "missing_variable_schema_entry" in var_issues


def test_strict_coverage_fails_on_expired_deprecations(tmp_path: Path, capsys) -> None:
    _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "coverage",
            "--strict",
            "--today",
            "2026-06-15",
            "--output",
            "json",
        ]
    )

    assert rc == 1
    functions_payload = json.loads(capsys.readouterr().out)
    function_items = {item["name"]: item for item in functions_payload["items"]}
    assert function_items["platform.expired"]["status"] == "failed"
    assert "expired_function_deprecation" in {
        issue["code"] for issue in functions_payload["issues"]
    }

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "coverage",
            "--strict",
            "--today",
            "2026-06-15",
            "--output",
            "json",
        ]
    )

    assert rc == 1
    vars_payload = json.loads(capsys.readouterr().out)
    vars_items = {item["key"]: item for item in vars_payload["items"]}
    assert vars_items["expired.topic.prefix"]["status"] == "failed"
    assert "expired_variable_deprecation" in {
        issue["code"] for issue in vars_payload["issues"]
    }


def test_catalog_generate_writes_markdown(tmp_path: Path, capsys) -> None:
    _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "catalog",
            "generate",
            "--output-file",
            "docs/functions-catalog.md",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "created"
    functions_doc = tmp_path / "docs/functions-catalog.md"
    assert functions_doc.exists()
    assert "| `platform.slug` |" in functions_doc.read_text(encoding="utf-8")

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "catalog",
            "generate",
            "--output-file",
            "docs/vars-catalog.md",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "created"
    vars_doc = tmp_path / "docs/vars-catalog.md"
    text = vars_doc.read_text(encoding="utf-8")
    assert "| `db.secret` |" in text
    assert "sensitive" in text


def test_rename_commands_return_safe_dry_run_plans(tmp_path: Path, capsys) -> None:
    manifest = _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "rename",
            "platform.slug",
            "platform.slug_v2",
            "--dry-run",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "function_rename_plan"
    assert payload["status"] == "planned"
    assert payload["from"] == "platform.slug"
    assert payload["to"] == "platform.slug_v2"
    assert payload["summary"]["affected_manifests"] == 1
    assert payload["changes"][0]["path"] == manifest.relative_to(tmp_path).as_posix()
    assert payload["changes"][0]["before"] == "platform.slug"
    assert payload["changes"][0]["after"] == "platform.slug_v2"

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "rename",
            "old.topic.prefix",
            "topic.prefix",
            "--dry-run",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "variable_rename_plan"
    assert payload["from"] == "old.topic.prefix"
    assert payload["to"] == "topic.prefix"
    assert payload["summary"]["affected_manifests"] == 1
    assert payload["changes"][0]["config_key"] == "legacy.topic"


def test_deprecate_commands_return_lifecycle_plans(tmp_path: Path, capsys) -> None:
    _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "deprecate",
            "platform.slug",
            "--replacement",
            "platform.slug_v2",
            "--remove-after",
            "2026-09-01",
            "--dry-run",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "function_deprecate_plan"
    assert payload["status"] == "planned"
    assert payload["function"]["name"] == "platform.slug"
    assert payload["lifecycle"]["replacement"] == "platform.slug_v2"
    assert payload["lifecycle"]["remove_after"] == "2026-09-01"
    assert payload["summary"]["affected_manifests"] == 1

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "deprecate",
            "old.topic.prefix",
            "--replacement",
            "topic.prefix",
            "--remove-after",
            "2026-09-01",
            "--dry-run",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "variable_deprecate_plan"
    assert payload["variable"]["key"] == "old.topic.prefix"
    assert payload["lifecycle"]["replacement"] == "topic.prefix"
    assert payload["lifecycle"]["remove_after"] == "2026-09-01"
