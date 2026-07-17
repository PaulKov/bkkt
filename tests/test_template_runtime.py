from __future__ import annotations

import json
from pathlib import Path

import pytest

from connectctl import cli
from connectctl.exceptions import ConnectCtlError
from connectctl.rendering.factory import build_renderer
from connectctl.settings import Settings
from connectctl.template_runtime import TemplateRuntime


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def _write_repo(tmp_path: Path, *, function_body: str) -> Path:
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
    (tmp_path / "bkkt/functions/custom.py").parent.mkdir(parents=True)
    (tmp_path / "bkkt/functions/custom.py").write_text(
        function_body,
        encoding="utf-8",
    )
    connector_dir = tmp_path / "connectors/demo/source/mariadb/connector_demo__demo"
    _write_json(
        connector_dir / "prod.demo.demo.source.mariadb.0.json",
        {
            "name": "prod.demo.demo.source.mariadb.0",
            "config": {
                "connector.class": "io.debezium.connector.mariadb.MariaDbConnector",
                "slugged.name": "${fn:slug(connector.name, max_len=15)}",
                "server.id": "${fn:hash_int(connector.name, mod=1000)}",
            },
        },
    )
    return connector_dir / "prod.demo.demo.source.mariadb.0.json"


def test_repo_function_loads_and_renders_with_function_context(tmp_path: Path) -> None:
    manifest = _write_repo(
        tmp_path,
        function_body="""
from connectctl.plugins import FunctionContext, bkkt_function

@bkkt_function(name="slug", description="Slugify a value")
def slug(value: str, *, max_len: int = 63, ctx: FunctionContext) -> str:
    assert ctx.variables.get("connector.name") == "prod.demo.demo.source.mariadb.0"
    return str(value).replace(".", "-")[:max_len]
""",
    )

    settings = Settings.load(tmp_path / "connectctl.yaml", repo_root=tmp_path)
    rr = build_renderer(settings).render(manifest)

    assert rr.manifest.config["slugged.name"] == "prod-demo-demo-"
    assert rr.manifest.config["server.id"].isdigit()


def test_repo_function_cannot_override_builtin(tmp_path: Path) -> None:
    _write_repo(
        tmp_path,
        function_body="""
from connectctl.plugins import bkkt_function

@bkkt_function(name="hash_int")
def not_allowed(value: str) -> str:
    return "1"
""",
    )
    settings = Settings.load(tmp_path / "connectctl.yaml", repo_root=tmp_path)

    with pytest.raises(ConnectCtlError, match="hash_int"):
        TemplateRuntime.from_settings(settings)


def test_repo_function_rejects_non_scalar_return(tmp_path: Path) -> None:
    manifest = _write_repo(
        tmp_path,
        function_body="""
from connectctl.plugins import bkkt_function

@bkkt_function(name="slug")
def slug(value: str, *, max_len: int = 63) -> dict:
    return {"bad": value}
""",
    )
    settings = Settings.load(tmp_path / "connectctl.yaml", repo_root=tmp_path)

    with pytest.raises(ConnectCtlError, match="must return scalar"):
        build_renderer(settings).render(manifest)


def test_functions_and_vars_cli_expose_repo_runtime_api(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = _write_repo(
        tmp_path,
        function_body="""
from connectctl.plugins import bkkt_function

@bkkt_function(name="slug", description="Slugify a value")
def slug(value: str, *, max_len: int = 63) -> str:
    return str(value).replace("_", "-")[:max_len]
""",
    )

    rc = cli.main(
        [
            "--repo-root",
            str(tmp_path),
            "--config",
            str(tmp_path / "connectctl.yaml"),
            "functions",
            "list",
            "--output",
            "json",
        ]
    )
    assert rc == 0
    listed = json.loads(capsys.readouterr().out)
    assert any(item["name"] == "slug" and item["source"] == "repo" for item in listed)

    rc = cli.main(
        [
            "--repo-root",
            str(tmp_path),
            "--config",
            str(tmp_path / "connectctl.yaml"),
            "functions",
            "run",
            "slug",
            "--arg",
            "A_B_C",
            "--kw",
            "max_len=3",
            "--manifest",
            str(manifest),
            "--output",
            "json",
        ]
    )
    assert rc == 0
    run_payload = json.loads(capsys.readouterr().out)
    assert run_payload["result"] == "A-B"
    assert run_payload["function"]["name"] == "slug"

    rc = cli.main(
        [
            "--repo-root",
            str(tmp_path),
            "--config",
            str(tmp_path / "connectctl.yaml"),
            "vars",
            "explain",
            str(manifest),
            "--output",
            "json",
        ]
    )
    assert rc == 0
    vars_payload = json.loads(capsys.readouterr().out)
    assert vars_payload["manifest"].endswith("prod.demo.demo.source.mariadb.0.json")
    assert "connector.name" in vars_payload["variables"]
