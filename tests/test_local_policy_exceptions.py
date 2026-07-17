from __future__ import annotations

from pathlib import Path

import yaml

from connectctl.models import (
    ConnectorManifest,
    ConnectorPathInfo,
    ConnectorType,
    Environment,
)
from connectctl.validation.local_policy_exceptions import (
    accepted_policy_exception_reason,
)
from connectctl.validation.policies_models import PolicyIssue


def _mk_manifest(root: Path, *, name: str, env: Environment) -> ConnectorManifest:
    source_path = root / "connector" / f"{name}.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("{}", encoding="utf-8")
    info = ConnectorPathInfo(
        path=source_path,
        relpath=Path(f"connector/{name}.json"),
        domain="bonus",
        connector_type=ConnectorType.sink,
        system="iceberg",
        connector_dir="connector_bonus__bonus_common",
        env=env,
        remainder="sink_raw_iceberg",
        mode=None,
    )
    return ConnectorManifest(
        name=name,
        config={"connector.class": "X", "name": name},
        source_path=source_path,
        info=info,
    )


def _write_drift(
    path: Path, *, connector_name_repo: str, env: str, repo_env: str
) -> None:
    export_dir = path.parent / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "drift.yaml").write_text(
        yaml.safe_dump(
            {
                "connector_name_repo": connector_name_repo,
                "env": env,
                "repo_env": repo_env,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_accepts_documented_cross_env_live_mapping(tmp_path: Path) -> None:
    manifest = _mk_manifest(
        tmp_path,
        name="prod.bonus.bonus_common.sink.raw.iceberg.1",
        env=Environment.prod,
    )
    _write_drift(
        manifest.source_path,
        connector_name_repo=manifest.name,
        env="stage",
        repo_env="prod",
    )
    issue = PolicyIssue(
        severity="error",
        policy="FOREIGN_ENV_REFERENCE",
        manifest_path=str(manifest.info.relpath),
        file_path=None,
        key="topics",
        message="x",
    )

    reason = accepted_policy_exception_reason(manifest=manifest, issue=issue)
    assert reason is not None
    assert "documented cross-env live mapping" in reason


def test_ignores_non_matching_or_same_env_drift(tmp_path: Path) -> None:
    manifest = _mk_manifest(
        tmp_path,
        name="prod.bonus.bonus_common.sink.raw.iceberg.1",
        env=Environment.prod,
    )
    _write_drift(
        manifest.source_path,
        connector_name_repo="other.connector",
        env="prod",
        repo_env="prod",
    )
    issue = PolicyIssue(
        severity="error",
        policy="BOOTSTRAP_HARDCODED",
        manifest_path=str(manifest.info.relpath),
        file_path=None,
        key="iceberg.kafka.bootstrap.servers",
        message="x",
    )

    assert accepted_policy_exception_reason(manifest=manifest, issue=issue) is None
