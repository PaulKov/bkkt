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


def _write_repo(tmp_path: Path, *, extra_config: str = "") -> Path:
    (tmp_path / "connectctl.yaml").write_text(
        f"""
connectors_root: connectors
default_cluster: acme-main
clusters:
  acme-main:
    prod:
      connect:
        scheme: http
        port: 8083
        hosts: ["127.0.0.1"]
{extra_config.rstrip()}
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
                "database.hostname": "${db.secret}",
                "topic.prefix": "${platform.topic_prefix}",
            },
        },
    )
    return manifest


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_provider(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "bkkt/var_providers/platform.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path


def _write_computed_var(tmp_path: Path) -> None:
    path = tmp_path / "bkkt/computed_vars/platform.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
from connectctl.plugins import ComputedVarContext, bkkt_computed_var

@bkkt_computed_var(name="platform.topic_prefix", depends_on=("db.secret",))
def topic_prefix(*, ctx: ComputedVarContext) -> str:
    return "cdc." + str(ctx.variables.get("db.secret")).replace("_", "-")
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_provider_injects_vars_before_computed_vars_and_render(
    tmp_path: Path, capsys
) -> None:
    manifest = _write_repo(tmp_path)
    _write_provider(
        tmp_path,
        """
from connectctl.plugins import VarProviderContext, bkkt_var_provider

@bkkt_var_provider(name="platform.db", description="Demo DB vars")
def provide_db(*, ctx: VarProviderContext) -> dict[str, str]:
    return {"db.secret": "dbz_" + str(ctx.variables.get("domain"))}
""",
    )
    _write_computed_var(tmp_path)

    rc = cli.main([*_repo_args(tmp_path), "render", str(manifest), "--output", "json"])

    assert rc == 0
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["config"]["database.hostname"] == "dbz_demo"
    assert rendered["config"]["topic.prefix"] == "cdc.dbz-demo"

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "explain",
            str(manifest),
            "db.secret",
            "--output",
            "json",
        ]
    )
    assert rc == 0
    explained = json.loads(capsys.readouterr().out)
    assert explained["sources"]["db.secret"] == "provider:platform.db"


def test_provider_shadowing_requires_explicit_allow_shadow(
    tmp_path: Path, capsys, caplog
) -> None:
    manifest = _write_repo(tmp_path)
    _write_json(
        manifest,
        {
            "name": "prod.demo.demo.source.postgres.0",
            "vars": {"db": {"secret": "repo-secret"}},
            "config": {"database.hostname": "${db.secret}"},
        },
    )
    _write_provider(
        tmp_path,
        """
from connectctl.plugins import VarProviderContext, bkkt_var_provider

@bkkt_var_provider(name="platform.db")
def provide_db(*, ctx: VarProviderContext) -> dict[str, str]:
    return {"db.secret": "provider-secret"}
""",
    )

    rc = cli.main([*_repo_args(tmp_path), "render", str(manifest)])

    assert rc == 2
    capsys.readouterr()
    assert "provider_shadowed_variable" in caplog.text
    assert "platform.db" in caplog.text
    assert "db.secret" in caplog.text

    _write_provider(
        tmp_path,
        """
from connectctl.plugins import VarProviderContext, bkkt_var_provider

@bkkt_var_provider(name="platform.db", allow_shadow=True)
def provide_db(*, ctx: VarProviderContext) -> dict[str, str]:
    return {"db.secret": "provider-secret"}
""",
    )

    rc = cli.main([*_repo_args(tmp_path), "render", str(manifest), "--output", "json"])

    assert rc == 0
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["config"]["database.hostname"] == "provider-secret"


def test_vars_providers_cli_list_explain_run_and_doctor(tmp_path: Path, capsys) -> None:
    manifest = _write_repo(tmp_path)
    _write_provider(
        tmp_path,
        """
from connectctl.plugins import VarProviderContext, bkkt_var_provider

@bkkt_var_provider(name="platform.db", description="Demo DB vars", provides=("db.secret",))
def provide_db(*, ctx: VarProviderContext) -> dict[str, str]:
    return {"db.secret": "dbz_" + str(ctx.variables.get("domain", "unknown"))}
""",
    )

    rc = cli.main(
        [*_repo_args(tmp_path), "vars", "providers", "list", "--output", "json"]
    )
    assert rc == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["providers"][0]["name"] == "platform.db"
    assert listed["providers"][0]["provides"] == ["db.secret"]

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "providers",
            "explain",
            "platform.db",
            "--output",
            "yaml",
        ]
    )
    assert rc == 0
    explained = yaml.safe_load(capsys.readouterr().out)
    assert explained["name"] == "platform.db"
    assert explained["description"] == "Demo DB vars"

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "providers",
            "run",
            "platform.db",
            "--manifest",
            str(manifest),
            "--output",
            "json",
        ]
    )
    assert rc == 0
    run = json.loads(capsys.readouterr().out)
    assert run["values"] == {"db.secret": "dbz_demo"}
    assert run["source"] == "provider:platform.db"

    rc = cli.main(
        [*_repo_args(tmp_path), "vars", "providers", "doctor", "--output", "json"]
    )
    assert rc == 0
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["status"] == "ok"
    assert doctor["summary"]["providers"] == 1


def test_provider_run_evaluates_only_selected_provider(tmp_path: Path, capsys) -> None:
    manifest = _write_repo(tmp_path)
    _write_provider(
        tmp_path,
        """
from connectctl.plugins import VarProviderContext, bkkt_var_provider

@bkkt_var_provider(name="platform.good")
def provide_good(*, ctx: VarProviderContext) -> dict[str, str]:
    return {"db.secret": "dbz_" + str(ctx.variables.get("domain"))}

@bkkt_var_provider(name="platform.broken")
def provide_broken(*, ctx: VarProviderContext) -> dict:
    raise RuntimeError("do not execute me")
""",
    )

    rc = cli.main(
        [
            *_repo_args(tmp_path),
            "vars",
            "providers",
            "run",
            "platform.good",
            "--manifest",
            str(manifest),
            "--output",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["values"] == {"db.secret": "dbz_demo"}


def test_provider_runtime_error_has_actionable_provider_context(
    tmp_path: Path, capsys, caplog
) -> None:
    manifest = _write_repo(tmp_path)
    _write_provider(
        tmp_path,
        """
from connectctl.plugins import VarProviderContext, bkkt_var_provider

@bkkt_var_provider(name="platform.broken")
def provide_broken(*, ctx: VarProviderContext) -> dict:
    raise RuntimeError("source system unavailable")
""",
    )

    rc = cli.main([*_repo_args(tmp_path), "render", str(manifest)])

    assert rc == 2
    capsys.readouterr()
    assert "Variable provider 'platform.broken' failed" in caplog.text
    assert "source system unavailable" in caplog.text


def test_provider_outputs_must_be_scalar(tmp_path: Path, capsys, caplog) -> None:
    manifest = _write_repo(tmp_path)
    _write_provider(
        tmp_path,
        """
from connectctl.plugins import VarProviderContext, bkkt_var_provider

@bkkt_var_provider(name="platform.bad")
def provide_bad(*, ctx: VarProviderContext) -> dict:
    return {"db.secret": {"nested": "not allowed"}}
""",
    )

    rc = cli.main([*_repo_args(tmp_path), "render", str(manifest)])

    assert rc == 2
    capsys.readouterr()
    assert "provider_value_type_mismatch" in caplog.text
    assert "platform.bad" in caplog.text


def test_function_runtime_blocks_disallowed_capability(
    tmp_path: Path, capsys, caplog
) -> None:
    manifest = _write_repo(
        tmp_path,
        extra_config="""
functions:
  runtime:
    allowed_capabilities: ["pure"]
""",
    )
    functions = tmp_path / "bkkt/functions/custom.py"
    functions.parent.mkdir(parents=True, exist_ok=True)
    functions.write_text(
        """
from connectctl.plugins import bkkt_function

@bkkt_function(name="platform.secret", capabilities=("network",))
def secret() -> str:
    return "dbz-network"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        manifest,
        {
            "name": "prod.demo.demo.source.postgres.0",
            "config": {"database.hostname": "${fn:platform.secret()}"},
        },
    )

    rc = cli.main([*_repo_args(tmp_path), "render", str(manifest)])

    assert rc == 2
    capsys.readouterr()
    assert "runtime_capability_denied" in caplog.text
    assert "platform.secret" in caplog.text
    assert "network" in caplog.text


def test_function_runtime_timeout_reports_function_name(
    tmp_path: Path, capsys, caplog
) -> None:
    manifest = _write_repo(
        tmp_path,
        extra_config="""
functions:
  runtime:
    max_call_ms: 1
""",
    )
    functions = tmp_path / "bkkt/functions/custom.py"
    functions.parent.mkdir(parents=True, exist_ok=True)
    functions.write_text(
        """
import time
from connectctl.plugins import bkkt_function

@bkkt_function(name="platform.slow")
def slow() -> str:
    time.sleep(0.02)
    return "too-slow"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        manifest,
        {
            "name": "prod.demo.demo.source.postgres.0",
            "config": {"database.hostname": "${fn:platform.slow()}"},
        },
    )

    rc = cli.main([*_repo_args(tmp_path), "render", str(manifest)])

    assert rc == 2
    capsys.readouterr()
    assert "runtime_timeout" in caplog.text
    assert "platform.slow" in caplog.text
