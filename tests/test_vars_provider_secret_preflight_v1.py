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
            "vars": {"domain": "demo"},
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "${secretManager:${db.secret}:host}",
                "database.user": "${secretManager:${db.secret}:username}",
            },
        },
    )
    return manifest


def _write_provider(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "bkkt/var_providers/platform.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path


def _write_provider_contract(tmp_path: Path) -> Path:
    path = tmp_path / "bkkt/var_providers/contracts/platform.db.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
version: 1
providers:
  platform.db:
    capabilities:
      - aws_secrets_read
    provides:
      db.secret:
        type: string
        pattern: "^dbz-"
        sensitive: true
      db.port:
        type: int
""",
        encoding="utf-8",
    )
    return path


def _write_secret_index(tmp_path: Path, *, keys: list[str]) -> Path:
    path = tmp_path / "bkkt/external_refs.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {"secretManager": {"dbz-demo-prod": {"keys": keys}}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def test_vars_preflight_validates_provider_contracts_and_secret_refs(
    tmp_path: Path, capsys
) -> None:
    manifest = _write_repo(tmp_path)
    _write_provider(
        tmp_path,
        """
from connectctl.plugins import VarProviderContext, bkkt_var_provider

@bkkt_var_provider(
    name="platform.db",
    description="Demo DB vars",
    provides=("db.secret", "db.port"),
    capabilities=("aws_secrets_read",),
)
def provide_db(*, ctx: VarProviderContext) -> dict[str, object]:
    return {"db.secret": "dbz-demo-prod", "db.port": 5432}
""",
    )
    contract = _write_provider_contract(tmp_path)
    secret_index = _write_secret_index(tmp_path, keys=["host", "username"])

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "preflight",
            str(manifest),
            "--provider-contract",
            str(contract),
            "--secret-index",
            str(secret_index),
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["summary"] == {
        "issues": 0,
        "provider_contracts": 1,
        "secret_refs": 2,
    }
    assert payload["provider_contracts"][0]["provider"] == "platform.db"
    assert payload["provider_contracts"][0]["status"] == "ok"
    assert payload["provider_contracts"][0]["values"]["db.secret"] == "<redacted>"
    assert payload["provider_contracts"][0]["values"]["db.port"] == 5432
    assert {item["field"] for item in payload["secret_refs"]} == {"host", "username"}
    assert all(item["status"] == "ok" for item in payload["secret_refs"])


def test_vars_preflight_fails_on_contract_and_secret_ref_issues(
    tmp_path: Path, capsys
) -> None:
    manifest = _write_repo(tmp_path)
    _write_provider(
        tmp_path,
        """
from connectctl.plugins import VarProviderContext, bkkt_var_provider

@bkkt_var_provider(
    name="platform.db",
    provides=("db.secret",),
    capabilities=("local_file_read",),
)
def provide_db(*, ctx: VarProviderContext) -> dict[str, object]:
    return {"db.secret": "plain-secret"}
""",
    )
    contract = _write_provider_contract(tmp_path)
    secret_index = _write_secret_index(tmp_path, keys=["host"])

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "preflight",
            str(manifest),
            "--provider-contract",
            str(contract),
            "--secret-index",
            str(secret_index),
            "--output",
            "json",
        ]
    )

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    codes = {issue["code"] for issue in payload["issues"]}
    assert codes == {
        "provider_capability_mismatch",
        "provider_contract_missing_output",
        "pattern_mismatch",
        "secret_not_found",
    }
    pattern_issue = next(
        issue for issue in payload["issues"] if issue["code"] == "pattern_mismatch"
    )
    assert pattern_issue["actual"] == "<redacted>"
    assert payload["provider_contracts"][0]["values"]["db.secret"] == "<redacted>"


def test_vars_providers_contract_infer_validate_and_test_cli(
    tmp_path: Path, capsys
) -> None:
    manifest = _write_repo(tmp_path)
    _write_provider(
        tmp_path,
        """
from connectctl.plugins import VarProviderContext, bkkt_var_provider

@bkkt_var_provider(name="platform.db", provides=("db.secret", "db.port"))
def provide_db(*, ctx: VarProviderContext) -> dict[str, object]:
    return {"db.secret": "dbz-demo-prod", "db.port": 5432}
""",
    )

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "providers",
            "contract",
            "infer",
            "platform.db",
            "--manifest",
            str(manifest),
            "--dry-run",
            "--output",
            "yaml",
        ]
    )
    assert rc == 0
    inferred = yaml.safe_load(capsys.readouterr().out)
    assert (
        inferred["providers"]["platform.db"]["provides"]["db.secret"]["type"]
        == "string"
    )
    assert inferred["providers"]["platform.db"]["provides"]["db.port"]["type"] == "int"

    contract_path = tmp_path / "bkkt/var_providers/contracts/platform.db.yaml"
    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "providers",
            "contract",
            "infer",
            "platform.db",
            "--manifest",
            str(manifest),
            "--output-file",
            str(contract_path),
        ]
    )
    assert rc == 0
    assert contract_path.exists()
    capsys.readouterr()

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "providers",
            "contract",
            "validate",
            "--manifest",
            str(manifest),
            "--contract",
            str(contract_path),
            "--output",
            "json",
        ]
    )
    assert rc == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["status"] == "ok"

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "providers",
            "test",
            "--manifest",
            str(manifest),
            "--contract",
            str(contract_path),
            "--output",
            "json",
        ]
    )
    assert rc == 0
    tested = json.loads(capsys.readouterr().out)
    assert tested["status"] == "ok"
