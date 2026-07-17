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
    _write_json(
        manifest,
        {
            "name": "prod.demo.demo.source.postgres.0",
            "vars": {
                "db": {"secret": "dbz-default-secret"},
                "retry": {"max": 34},
            },
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "${db.secret}",
                "topic.prefix": "cdc.${fn:platform.slug(connector.name, max_len=12)}",
            },
        },
    )
    return manifest


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_functions(tmp_path: Path, body: str) -> None:
    functions_file = tmp_path / "bkkt/functions/custom.py"
    functions_file.parent.mkdir(parents=True, exist_ok=True)
    functions_file.write_text(body, encoding="utf-8")


def _write_platform_slug(tmp_path: Path) -> None:
    _write_functions(
        tmp_path,
        """
from connectctl.plugins import bkkt_function

@bkkt_function(name="platform.slug")
def slug(value: str, *, max_len: int = 63) -> str:
    return str(value).lower().replace(".", "-")[:max_len]
""",
    )


def _write_schema(tmp_path: Path) -> None:
    schema = tmp_path / "bkkt/vars.schema.yaml"
    schema.parent.mkdir(parents=True, exist_ok=True)
    schema.write_text(
        """
version: 1
vars:
  db.secret:
    type: string
    required: true
    sensitive: true
    description: Database secret name
  retry.max:
    type: int
    required: true
""",
        encoding="utf-8",
    )


def test_namespaced_function_call_and_typed_signature_errors(
    tmp_path: Path, capsys, caplog
) -> None:
    manifest = _write_repo(tmp_path)
    _write_functions(
        tmp_path,
        """
from connectctl.plugins import bkkt_function

@bkkt_function(name="platform.slug", description="Normalize connector fragments")
def slug(value: str, *, max_len: int = 63) -> str:
    return str(value).lower().replace(".", "-")[:max_len]
""",
    )

    rc = cli.main([*_repo_args(tmp_path), "render", str(manifest), "--output", "json"])

    assert rc == 0
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["config"]["topic.prefix"] == "cdc.prod-demo-de"

    bad_manifest = manifest.with_name("prod.demo.bad.source.postgres.0.json")
    _write_json(
        bad_manifest,
        {
            "name": "prod.demo.bad.source.postgres.0",
            "config": {
                "topic.prefix": "${fn:platform.slug(connector.name, max_len='bad')}",
            },
        },
    )

    rc = cli.main([*_repo_args(tmp_path), "render", str(bad_manifest)])

    assert rc == 2
    capsys.readouterr()
    err = caplog.text
    assert "function_arg_type_mismatch" in err
    assert "platform.slug" in err
    assert "max_len" in err


def test_sensitive_vars_are_redacted_in_explain_trace_and_docs(
    tmp_path: Path, capsys
) -> None:
    manifest = _write_repo(tmp_path)
    _write_platform_slug(tmp_path)
    _write_schema(tmp_path)
    secret = "dbz-default-secret"

    rc = cli.main(
        [*_repo_args(tmp_path), "vars", "explain", str(manifest), "--output", "json"]
    )

    assert rc == 0
    explain = capsys.readouterr().out
    assert secret not in explain
    assert "<redacted>" in explain

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "trace",
            str(manifest),
            "db.secret",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    trace = capsys.readouterr().out
    assert secret not in trace
    assert "<redacted>" in trace

    docs_file = tmp_path / "docs/BKKT_VARS.md"
    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "docs",
            "generate",
            "--output-file",
            str(docs_file),
        ]
    )

    assert rc == 0
    docs = docs_file.read_text(encoding="utf-8")
    assert "db.secret" in docs
    assert "Sensitive" in docs
    assert secret not in docs


def test_vars_profile_can_drive_render_and_diff(tmp_path: Path, capsys) -> None:
    manifest = _write_repo(tmp_path)
    _write_platform_slug(tmp_path)
    profile = tmp_path / "bkkt/vars/profiles/replica-switch.yaml"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(
        """
name: replica-switch
description: Switch DB secret for replica migration dry-runs.
vars:
  db:
    secret: dbz-replica-secret
""",
        encoding="utf-8",
    )

    rc = cli.main(
        [*_repo_args(tmp_path), "vars", "profile", "list", "--output", "json"]
    )

    assert rc == 0
    profiles = json.loads(capsys.readouterr().out)
    assert profiles["summary"]["profiles"] == 1
    assert profiles["profiles"][0]["name"] == "replica-switch"

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "render",
            str(manifest),
            "--vars-profile",
            "replica-switch",
            "--output",
            "json",
        ]
    )

    assert rc == 0
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["config"]["database.hostname"] == "dbz-replica-secret"

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "profile",
            "diff",
            "replica-switch",
            str(manifest),
            "--output",
            "yaml",
        ]
    )

    assert rc == 0
    diff = yaml.safe_load(capsys.readouterr().out)
    assert diff["profile"] == "replica-switch"
    assert diff["changes"][0]["key"] == "db.secret"
    assert diff["changes"][0]["before"] == "dbz-default-secret"
    assert diff["changes"][0]["after"] == "dbz-replica-secret"


def test_strict_doctor_requires_capability_for_network_function(
    tmp_path: Path, capsys
) -> None:
    _write_repo(tmp_path)
    _write_functions(
        tmp_path,
        """
import requests
from connectctl.plugins import bkkt_function

@bkkt_function(name="net.fetch")
def fetch(value: str) -> str:
    return str(value)
""",
    )

    rc = cli.main(
        [*_repo_args(tmp_path), "functions", "doctor", "--strict", "--output", "json"]
    )

    assert rc == 1
    failed = json.loads(capsys.readouterr().out)
    assert failed["strict_issues"][0]["code"] == "risky_import"
    assert failed["strict_issues"][0]["required_capability"] == "network"

    _write_functions(
        tmp_path,
        """
import requests
from connectctl.plugins import bkkt_function

@bkkt_function(name="net.fetch", capabilities=("network",))
def fetch(value: str) -> str:
    return str(value)
""",
    )

    rc = cli.main(
        [*_repo_args(tmp_path), "functions", "doctor", "--strict", "--output", "json"]
    )

    assert rc == 0
    passed = json.loads(capsys.readouterr().out)
    assert passed["strict_issues"] == []


def test_function_package_list_and_docs_group_namespaces(
    tmp_path: Path, capsys
) -> None:
    _write_repo(tmp_path)
    _write_functions(
        tmp_path,
        """
from connectctl.plugins import bkkt_function

@bkkt_function(name="platform.slug")
def platform_slug(value: str) -> str:
    return str(value)

@bkkt_function(name="topx.route")
def topx_route(value: str) -> str:
    return str(value)

@bkkt_function(name="legacy")
def legacy(value: str) -> str:
    return str(value)
""",
    )

    rc = cli.main(
        [*_repo_args(tmp_path), "functions", "package", "list", "--output", "json"]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert {item["name"] for item in payload["packages"]} >= {
        "default",
        "platform",
        "topx",
    }
    platform = next(item for item in payload["packages"] if item["name"] == "platform")
    assert platform["functions"] == ["platform.slug"]

    docs_file = tmp_path / "docs/BKKT_FUNCTIONS_PLATFORM.md"
    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "functions",
            "package",
            "docs",
            "generate",
            "platform",
            "--output-file",
            str(docs_file),
        ]
    )

    assert rc == 0
    docs = docs_file.read_text(encoding="utf-8")
    assert "# BKKT Function Package `platform`" in docs
    assert "`platform.slug`" in docs
    assert "`topx.route`" not in docs
