from __future__ import annotations

import json
from pathlib import Path

import yaml

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


def _write_repo(tmp_path: Path) -> tuple[Path, Path]:
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
    first = (
        tmp_path
        / "connectors/demo/source/postgres/connector_demo__demo/prod.demo.demo.source.postgres.0.json"
    )
    second = (
        tmp_path
        / "connectors/demo/source/postgres/connector_demo__bad/prod.demo.bad.source.postgres.0.json"
    )
    _write_json(
        first,
        {
            "name": "prod.demo.demo.source.postgres.0",
            "vars": {"db": {"secret": "dbz-demo-prod"}, "retry": {"max": 34}},
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "${secretManager:${db.secret}:host}",
                "errors.max.retries": "${retry.max}",
            },
        },
    )
    _write_json(
        second,
        {
            "name": "prod.demo.bad.source.postgres.0",
            "vars": {"db": {"secret": "plain-secret"}},
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "${secretManager:${db.secret}:host}",
            },
        },
    )
    return first, second


def test_vars_schema_infer_from_repo_and_validate_repo(tmp_path: Path, capsys) -> None:
    _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "schema",
            "infer",
            "--from-repo",
            "--dry-run",
            "--output",
            "yaml",
        ]
    )
    assert rc == 0
    inferred = yaml.safe_load(capsys.readouterr().out)
    assert inferred["version"] == 1
    assert inferred["vars"]["db.secret"]["type"] == "string"
    assert inferred["vars"]["retry.max"]["type"] == "int"
    assert inferred["vars"]["db.secret"]["required"] is False

    schema_path = tmp_path / "bkkt/vars.schema.yaml"
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(
        """
version: 1
vars:
  db.secret:
    type: string
    pattern: "^dbz-"
""",
        encoding="utf-8",
    )

    rc = cli.main([*_repo_args(tmp_path), "vars", "validate-repo", "--output", "json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["summary"]["manifests"] == 2
    assert payload["summary"]["failed"] == 1
    assert payload["results"][0]["manifest"].endswith(
        "prod.demo.bad.source.postgres.0.json"
    )
    assert payload["results"][0]["issues"][0]["code"] == "pattern_mismatch"


def test_vars_computed_scaffold_writes_function_and_contract(tmp_path: Path) -> None:
    _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "computed",
            "scaffold",
            "platform.topic_prefix",
            "--path",
            "bkkt/computed_vars/platform.py",
            "--test-path",
            "bkkt/computed_vars/tests/platform.yaml",
        ]
    )

    assert rc == 0
    function_file = tmp_path / "bkkt/computed_vars/platform.py"
    test_file = tmp_path / "bkkt/computed_vars/tests/platform.yaml"
    assert '@bkkt_computed_var(name="platform.topic_prefix"' in function_file.read_text(
        encoding="utf-8"
    )
    assert "variable: platform.topic_prefix" in test_file.read_text(encoding="utf-8")


def test_functions_contract_infer_dry_run_and_write(tmp_path: Path, capsys) -> None:
    _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "contract",
            "infer",
            "slug",
            "--arg",
            "MY_VALUE",
            "--kw",
            "max_len=4",
            "--expect",
            "my-v",
            "--dry-run",
            "--output",
            "yaml",
        ]
    )
    assert rc == 0
    dry_run = yaml.safe_load(capsys.readouterr().out)
    assert dry_run["cases"][0]["function"] == "slug"
    assert dry_run["cases"][0]["args"] == ["MY_VALUE"]
    assert dry_run["cases"][0]["kwargs"] == {"max_len": 4}
    assert dry_run["cases"][0]["expect"] == "my-v"

    output_file = tmp_path / "bkkt/functions/tests/slug.yaml"
    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "contract",
            "infer",
            "slug",
            "--arg",
            "MY_VALUE",
            "--expect",
            "my-value",
            "--output-file",
            str(output_file),
        ]
    )
    assert rc == 0
    assert output_file.exists()
    assert "function: slug" in output_file.read_text(encoding="utf-8")


def test_functions_doctor_strict_reports_signature_issues(
    tmp_path: Path, capsys
) -> None:
    _write_repo(tmp_path)
    functions_file = tmp_path / "bkkt/functions/custom.py"
    functions_file.parent.mkdir(parents=True, exist_ok=True)
    functions_file.write_text(
        """
from connectctl.plugins import bkkt_function

@bkkt_function(name="bad_signature")
def bad_signature(value, ctx):
    return str(value)
""",
        encoding="utf-8",
    )

    rc = cli.main(
        [*_repo_args(tmp_path), "functions", "doctor", "--strict", "--output", "json"]
    )

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    codes = {issue["code"] for issue in payload["strict_issues"]}
    assert "signature_missing_parameter_annotation" in codes
    assert "signature_missing_return_annotation" in codes
    assert "signature_ctx_untyped" in codes
