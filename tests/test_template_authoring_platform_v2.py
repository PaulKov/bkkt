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
    functions_file = tmp_path / "bkkt/functions/custom.py"
    functions_file.parent.mkdir(parents=True, exist_ok=True)
    functions_file.write_text(
        """
from connectctl.plugins import FunctionContext, bkkt_function


@bkkt_function(name="slug", description="Normalize connector identifiers")
def slug(value: str, *, max_len: int = 63, ctx: FunctionContext) -> str:
    return str(value).replace(".", "-").lower()[:max_len]
""",
        encoding="utf-8",
    )
    computed_file = tmp_path / "bkkt/computed_vars/platform.py"
    computed_file.parent.mkdir(parents=True, exist_ok=True)
    computed_file.write_text(
        """
from connectctl.plugins import ComputedVarContext, bkkt_computed_var


@bkkt_computed_var(name="platform.topic_prefix")
def topic_prefix(ctx: ComputedVarContext) -> str:
    return "cdc." + str(ctx.variables.get("connector.name")).replace(".", "-")
""",
        encoding="utf-8",
    )
    good_manifest = (
        tmp_path
        / "connectors/demo/source/postgres/connector_demo__demo/prod.demo.demo.source.postgres.0.json"
    )
    bad_manifest = (
        tmp_path
        / "connectors/demo/source/postgres/connector_demo__bad/prod.demo.bad.source.postgres.0.json"
    )
    _write_json(
        good_manifest,
        {
            "name": "prod.demo.demo.source.postgres.0",
            "vars": {"db": {"secret": "dbz-demo-prod"}, "retry": {"max": 34}},
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "${secretManager:${db.secret}:host}",
                "errors.max.retries": "${retry.max}",
                "topic.prefix": "${platform.topic_prefix}",
                "name.normalized": "${fn:slug(connector.name, max_len=12)}",
            },
        },
    )
    _write_json(
        bad_manifest,
        {
            "name": "prod.demo.bad.source.postgres.0",
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "bad.normalized": "${fn:slug(connector.name, max_len='bad')}",
            },
        },
    )
    return good_manifest, bad_manifest


def test_render_trace_explains_config_key(tmp_path: Path, capsys) -> None:
    manifest, _ = _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "render",
            "trace",
            str(manifest.relative_to(tmp_path)),
            "--config-key",
            "topic.prefix",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["config_key"] == "topic.prefix"
    assert payload["final_value"] == "cdc.prod-demo-demo-source-postgres-0"
    step_kinds = [step["kind"] for step in payload["steps"]]
    assert "config_source" in step_kinds
    assert "variable" in step_kinds
    variable_steps = {
        step["name"]: step for step in payload["steps"] if step["kind"] == "variable"
    }
    assert (
        variable_steps["platform.topic_prefix"]["source"]
        == "computed:platform.topic_prefix"
    )


def test_render_trace_includes_variable_contract_metadata(
    tmp_path: Path, capsys
) -> None:
    manifest, _ = _write_repo(tmp_path)
    schema = tmp_path / "bkkt/vars.schema.yaml"
    schema.parent.mkdir(parents=True, exist_ok=True)
    schema.write_text(
        """
version: 1
vars:
  db.secret:
    type: string
    required: true
    pattern: "^dbz-"
    sensitive: true
    description: "Database secret name"
""",
        encoding="utf-8",
    )

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "render",
            "trace",
            str(manifest.relative_to(tmp_path)),
            "--config-key",
            "database.hostname",
            "--include-contracts",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["contracts"]["summary"] == {
        "variables": 1,
        "errors": 0,
        "warnings": 0,
    }
    variable_steps = {
        step["name"]: step for step in payload["steps"] if step["kind"] == "variable"
    }
    db_secret = variable_steps["db.secret"]
    assert db_secret["value"] == "<redacted>"
    assert db_secret["contract"]["status"] == "ok"
    assert db_secret["contract"]["type"] == "string"
    assert db_secret["contract"]["required"] is True
    assert db_secret["contract"]["sensitive"] is True


def test_render_trace_surfaces_variable_contract_issues(tmp_path: Path, capsys) -> None:
    manifest, _ = _write_repo(tmp_path)
    schema = tmp_path / "bkkt/vars.schema.yaml"
    schema.parent.mkdir(parents=True, exist_ok=True)
    schema.write_text(
        """
version: 1
vars:
  db.secret:
    type: string
    required: true
    pattern: "^vault-"
    sensitive: true
""",
        encoding="utf-8",
    )

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "render",
            "trace",
            str(manifest.relative_to(tmp_path)),
            "--config-key",
            "database.hostname",
            "--include-contracts",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["contracts"]["summary"] == {
        "variables": 1,
        "errors": 1,
        "warnings": 0,
    }
    variable_steps = {
        step["name"]: step for step in payload["steps"] if step["kind"] == "variable"
    }
    db_secret = variable_steps["db.secret"]
    assert db_secret["value"] == "<redacted>"
    assert db_secret["contract"]["status"] == "failed"
    assert db_secret["contract"]["issues"][0]["code"] == "pattern_mismatch"


def test_vars_trace_explains_value_and_usages(tmp_path: Path, capsys) -> None:
    manifest, _ = _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "trace",
            str(manifest.relative_to(tmp_path)),
            "db.secret",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["variable"] == "db.secret"
    assert payload["value"] == "dbz-demo-prod"
    assert payload["source"].endswith("prod.demo.demo.source.postgres.0.json")
    assert payload["usages"] == [
        {
            "config_key": "database.hostname",
            "kind": "placeholder",
            "via_function": None,
        }
    ]


def test_functions_validate_calls_reports_literal_type_mismatch(
    tmp_path: Path, capsys
) -> None:
    _, manifest = _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "validate-calls",
            str(manifest.relative_to(tmp_path)),
            "--output",
            "json",
        ]
    )

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["summary"] == {"errors": 1, "warnings": 1, "total": 2}
    assert payload["issues"][0]["code"] == "function_arg_type_mismatch"
    assert payload["issues"][0]["function"] == "slug"
    assert payload["issues"][0]["parameter"] == "max_len"
    assert payload["issues"][0]["expected"] == "int"
    assert payload["issues"][0]["actual_type"] == "str"
    assert payload["issues"][1]["code"] == "function_arg_type_unknown"
