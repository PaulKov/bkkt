from __future__ import annotations

import json
from pathlib import Path

from connectctl import cli


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
      render:
        vars:
          server_id_namespace: prod-main
""",
        encoding="utf-8",
    )
    (tmp_path / "bkkt/functions/custom.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "bkkt/functions/custom.py").write_text(
        """
from connectctl.plugins import bkkt_function

@bkkt_function(name="slug", description="Normalize connector names")
def slug(value: str, *, max_len: int = 63) -> str:
    return str(value).lower().replace(".", "-")[:max_len]

@bkkt_function(name="unused_helper", description="Unused helper")
def unused_helper(value: str) -> str:
    return str(value)
""",
        encoding="utf-8",
    )
    (tmp_path / "bkkt/vars.schema.yaml").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "bkkt/vars.schema.yaml").write_text(
        """
version: 1
vars:
  db.secret:
    type: string
    required: true
  retry.max:
    type: int
  unused.value:
    type: string
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
                "retry": {"max": 34},
            },
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "${secretManager:${db.secret}:host}",
                "topic.prefix": "cdc.${fn:slug(connector.name, max_len=24)}",
                "errors.max.retries": "${retry.max}",
            },
        },
    )
    second = (
        tmp_path
        / "connectors/demo/sink/iceberg/connector_demo__demo/prod.demo.demo.sink.raw.iceberg.0.json"
    )
    _write_json(
        second,
        {
            "name": "prod.demo.demo.sink.raw.iceberg.0",
            "config": {
                "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
                "topics": "cdc.${fn:slug(connector.name, max_len=10)}",
            },
        },
    )
    return manifest, second


def test_vars_and_functions_used_by_report_repo_wide_impact(
    tmp_path: Path, capsys
) -> None:
    manifest, _ = _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "used-by",
            "db.secret",
            "--output",
            "json",
        ]
    )
    assert rc == 0
    vars_payload = json.loads(capsys.readouterr().out)
    assert vars_payload["query"] == {"kind": "variable", "name": "db.secret"}
    assert vars_payload["summary"]["matches"] == 1
    assert vars_payload["matches"][0]["manifest"].endswith(manifest.name)
    assert vars_payload["matches"][0]["config_key"] == "database.hostname"

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "used-by",
            "slug",
            "--output",
            "json",
        ]
    )
    assert rc == 0
    functions_payload = json.loads(capsys.readouterr().out)
    assert functions_payload["query"] == {"kind": "function", "name": "slug"}
    assert functions_payload["summary"]["matches"] == 2
    assert {m["config_key"] for m in functions_payload["matches"]} == {
        "topic.prefix",
        "topics",
    }


def test_vars_and_functions_lint_report_unused_declarations(
    tmp_path: Path, capsys
) -> None:
    _write_repo(tmp_path)

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "lint",
            "--unused",
            "--output",
            "json",
        ]
    )
    assert rc == 1
    vars_payload = json.loads(capsys.readouterr().out)
    assert vars_payload["status"] == "failed"
    assert vars_payload["issues"] == [
        {
            "code": "unused_var",
            "name": "unused.value",
            "message": "Variable 'unused.value' is declared but not used by any manifest",
        }
    ]

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "lint",
            "--unused",
            "--output",
            "json",
        ]
    )
    assert rc == 1
    functions_payload = json.loads(capsys.readouterr().out)
    assert functions_payload["status"] == "failed"
    assert functions_payload["issues"][0]["code"] == "unused_function"
    assert functions_payload["issues"][0]["name"] == "unused_helper"


def test_functions_and_vars_docs_generate_markdown(tmp_path: Path, capsys) -> None:
    _write_repo(tmp_path)
    functions_doc = tmp_path / "artifacts/functions.md"
    vars_doc = tmp_path / "artifacts/vars.md"

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "docs",
            "generate",
            "--output-file",
            str(functions_doc),
        ]
    )
    assert rc == 0
    assert "Generated" in capsys.readouterr().out
    assert "slug" in functions_doc.read_text(encoding="utf-8")
    assert "unused_helper" in functions_doc.read_text(encoding="utf-8")

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "docs",
            "generate",
            "--output-file",
            str(vars_doc),
        ]
    )
    assert rc == 0
    assert "Generated" in capsys.readouterr().out
    vars_text = vars_doc.read_text(encoding="utf-8")
    assert "db.secret" in vars_text
    assert "unused.value" in vars_text
