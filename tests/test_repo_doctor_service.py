from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace


from connectctl.adapters.filesystem_memory import InMemoryFileSystem
from connectctl.config_models import (
    ExportConfig,
    NamingConfig,
    SafetyConfig,
    SyncConfig,
)
from connectctl.models import ConnectClusterConfig, Environment, RepoConfig
from connectctl.services.repo_doctor.service import RepoDoctorService
from connectctl.settings_models import Settings, TagSettings


def _mk_settings(repo_root: Path, *, ignore_dirs=()) -> Settings:
    repo_cfg = RepoConfig(
        root=repo_root, connectors_root=repo_root, ignore_dirs=tuple(ignore_dirs)
    )
    cc = ConnectClusterConfig(
        env=Environment.dev, urls=["http://localhost:8083"], name="acme-main"
    )
    groups = {"acme-main": {Environment.dev: cc}}
    return Settings(
        repo=repo_cfg,
        clusters=dict(groups["acme-main"]),
        cluster_groups=groups,
        default_cluster="acme-main",
        tags=TagSettings(definitions={}, hard_conflict_params=("cluster",)),
        naming=NamingConfig(enabled=True, strict=True, rules=()),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={},
    )


def test_repo_doctor_reports_missing_helper_dirs(capsys):
    fs = InMemoryFileSystem()
    fs.mkdirs(Path("/repo"), exist_ok=True)

    settings = _mk_settings(Path("/repo"), ignore_dirs=(".git",))
    ctx = SimpleNamespace(
        repo_root=Path("/repo"),
        fs=fs,
        logger=None,
        settings=settings,
        config_path=Path("/repo/connectctl.yaml"),
    )

    svc = RepoDoctorService(ctx=ctx)
    rc = svc.run(Namespace(strict=False))
    assert rc == 0

    out = capsys.readouterr().out
    assert "Repo doctor" in out
    assert "__global/ is missing" in out
    assert "init templates dir is missing" in out


def test_repo_doctor_strict_fails_on_warn(capsys):
    fs = InMemoryFileSystem()
    fs.mkdirs(Path("/repo"), exist_ok=True)

    settings = _mk_settings(Path("/repo"), ignore_dirs=(".git",))
    ctx = SimpleNamespace(
        repo_root=Path("/repo"),
        fs=fs,
        logger=None,
        settings=settings,
        config_path=Path("/repo/connectctl.yaml"),
    )

    svc = RepoDoctorService(ctx=ctx)
    rc = svc.run(Namespace(strict=True))
    assert rc == 2
