from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

from connectctl.function_locks import FunctionLockService
from connectctl.settings import Settings


def write_repo(root: Path, body: str) -> Path:
    (root / "connectctl.yaml").write_text(
        textwrap.dedent(
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
            functions:
              enabled: true
              paths:
                - bkkt/functions
              allow_repo_python: true
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    fn_path = root / "bkkt/functions/platform.py"
    fn_path.parent.mkdir(parents=True, exist_ok=True)
    fn_path.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")
    return fn_path


def load_service(root: Path) -> FunctionLockService:
    settings = Settings.load(root / "connectctl.yaml", repo_root=root)
    return FunctionLockService(settings)


def test_lockfile_is_stable_and_contains_function_fingerprints(tmp_path: Path) -> None:
    write_repo(
        tmp_path,
        """
        from connectctl.plugins import FunctionContext, bkkt_function

        @bkkt_function(name="platform.slug", description="Slugify", capabilities=("filesystem",))
        def slug(value: str, *, ctx: FunctionContext) -> str:
            return value.lower()
        """,
    )

    payload = load_service(tmp_path).build_lock_payload()

    assert payload["version"] == 1
    assert payload["packages"][0]["name"] == "platform"
    item = payload["packages"][0]["functions"][0]
    assert item["name"] == "platform.slug"
    assert item["capabilities"] == ["filesystem"]
    assert item["fingerprint"].startswith("sha256:")
    assert item["source_path"] == "bkkt/functions/platform.py"


def test_check_fails_when_function_changed_without_updated_lock(
    tmp_path: Path,
) -> None:
    write_repo(
        tmp_path,
        """
        from connectctl.plugins import FunctionContext, bkkt_function

        @bkkt_function(name="platform.slug", description="Slugify")
        def slug(value: str, *, ctx: FunctionContext) -> str:
            return value.lower()
        """,
    )
    service = load_service(tmp_path)
    service.write_lock(tmp_path / "bkkt/functions.lock.yaml")
    write_repo(
        tmp_path,
        """
        from connectctl.plugins import FunctionContext, bkkt_function

        @bkkt_function(name="platform.slug", description="Slugify")
        def slug(value: str, *, ctx: FunctionContext) -> str:
            return value.upper()
        """,
    )

    result = load_service(tmp_path).check_lock(
        lock_path=tmp_path / "bkkt/functions.lock.yaml"
    )

    assert result.status == "failed"
    assert result.issues[0].code == "function_fingerprint_changed"
    assert result.issues[0].function == "platform.slug"


def test_impact_gate_requires_artifact_for_changed_used_function(
    tmp_path: Path,
) -> None:
    write_repo(
        tmp_path,
        """
        from connectctl.plugins import FunctionContext, bkkt_function

        @bkkt_function(name="platform.slug", description="Slugify")
        def slug(value: str, *, ctx: FunctionContext) -> str:
            return value.lower()
        """,
    )
    connector = tmp_path / "connectors/prod.example.source.postgres.0.json"
    connector.parent.mkdir(parents=True)
    connector.write_text(
        json.dumps(
            {
                "connectctl": {"env": "prod", "cluster": "acme-main"},
                "config": {"topic.prefix": "${fn:platform.slug(connector.name)}"},
            }
        ),
        encoding="utf-8",
    )
    service = load_service(tmp_path)
    service.write_lock(tmp_path / "bkkt/functions.lock.yaml")
    write_repo(
        tmp_path,
        """
        from connectctl.plugins import FunctionContext, bkkt_function

        @bkkt_function(name="platform.slug", description="Slugify")
        def slug(value: str, *, ctx: FunctionContext) -> str:
            return value.upper()
        """,
    )

    result = load_service(tmp_path).gate(
        lock_path=tmp_path / "bkkt/functions.lock.yaml"
    )

    assert result.status == "failed"
    impact_issue = next(
        issue
        for issue in result.issues
        if issue.code == "missing_function_impact_artifact"
    )
    assert impact_issue.function == "platform.slug"
    assert impact_issue.manifest == "connectors/prod.example.source.postgres.0.json"


def test_impact_gate_passes_when_changed_function_is_acknowledged(
    tmp_path: Path,
) -> None:
    write_repo(
        tmp_path,
        """
        from connectctl.plugins import FunctionContext, bkkt_function

        @bkkt_function(name="platform.slug", description="Slugify")
        def slug(value: str, *, ctx: FunctionContext) -> str:
            return value.lower()
        """,
    )
    connector = tmp_path / "connectors/prod.example.source.postgres.0.json"
    connector.parent.mkdir(parents=True)
    connector.write_text(
        json.dumps(
            {
                "connectctl": {"env": "prod", "cluster": "acme-main"},
                "config": {"topic.prefix": "${fn:platform.slug(connector.name)}"},
            }
        ),
        encoding="utf-8",
    )
    service = load_service(tmp_path)
    service.write_lock(tmp_path / "bkkt/functions.lock.yaml")
    artifact = tmp_path / "artifacts/function-impact.yaml"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("functions:\n  - platform.slug\n", encoding="utf-8")
    write_repo(
        tmp_path,
        """
        from connectctl.plugins import FunctionContext, bkkt_function

        @bkkt_function(name="platform.slug", description="Slugify")
        def slug(value: str, *, ctx: FunctionContext) -> str:
            return value.upper()
        """,
    )

    result = load_service(tmp_path).gate(
        lock_path=tmp_path / "bkkt/functions.lock.yaml",
        impact_artifact=artifact,
    )

    assert result.status == "ok"
    assert result.changes[0].function == "platform.slug"
    assert result.issues == ()


def test_cli_generates_lock_and_reports_diff(tmp_path: Path) -> None:
    write_repo(
        tmp_path,
        """
        from connectctl.plugins import FunctionContext, bkkt_function

        @bkkt_function(name="platform.slug", description="Slugify")
        def slug(value: str, *, ctx: FunctionContext) -> str:
            return value.lower()
        """,
    )

    cmd = [sys.executable, "-m", "connectctl.cli"]
    subprocess.run(
        cmd + ["functions", "package", "lock", "--write"],
        cwd=tmp_path,
        check=True,
    )
    assert (tmp_path / "bkkt/functions.lock.yaml").exists()
    result = subprocess.run(
        cmd + ["functions", "package", "diff", "--output", "json"],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["summary"]["changes"] == 0
