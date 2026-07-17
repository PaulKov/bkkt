from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from connectctl.adapters.filesystem_memory import InMemoryFileSystem
from connectctl.exceptions import ConfigError
from connectctl.services.repo_bootstrap.service import RepoBootstrapService


def test_repo_bootstrap_full_creates_connectctl_global_and_init_templates() -> None:
    fs = InMemoryFileSystem()
    ctx = SimpleNamespace(repo_root=Path("/repo"), fs=fs, logger=None)
    svc = RepoBootstrapService(ctx=ctx)

    args = Namespace(
        preset="full",
        only=None,
        init_templates_root=None,
        force=False,
        update=False,
        dry_run=False,
    )

    svc.run(args)

    assert fs.exists(Path("/repo/connectctl.yaml"))
    assert fs.exists(Path("/repo/__global/all.json"))
    assert fs.exists(Path("/repo/__global/source/all.json"))
    assert fs.exists(Path("/repo/__init_templates/README.md"))
    assert fs.exists(Path("/repo/__init_templates/__global/all.json"))


def test_repo_bootstrap_only_connectctl_creates_single_config_file() -> None:
    fs = InMemoryFileSystem()
    ctx = SimpleNamespace(repo_root=Path("/repo"), fs=fs, logger=None)
    svc = RepoBootstrapService(ctx=ctx)

    args = Namespace(
        preset="full",
        only=["connectctl"],
        init_templates_root=None,
        force=False,
        update=False,
        dry_run=False,
    )

    svc.run(args)

    cfg = Path("/repo/connectctl.yaml")
    assert fs.exists(cfg)
    text = fs.read_text(cfg)
    assert "default_cluster: default" in text
    assert "127.0.0.1" in text
    assert not fs.exists(Path("/repo/__global"))


def test_repo_bootstrap_update_writes_dist_for_modified_file() -> None:
    fs = InMemoryFileSystem()
    ctx = SimpleNamespace(repo_root=Path("/repo"), fs=fs, logger=None)
    svc = RepoBootstrapService(ctx=ctx)

    args = Namespace(
        preset="full",
        only=None,
        init_templates_root=None,
        force=False,
        update=False,
        dry_run=False,
    )
    svc.run(args)

    target = Path("/repo/__global/all.json")
    original = fs.read_text(target)

    # Simulate user customization.
    fs.write_text(target, original + "\n# user-change\n")

    args2 = Namespace(
        preset="full",
        only=None,
        init_templates_root=None,
        force=False,
        update=True,
        dry_run=False,
    )
    svc.run(args2)

    # Main file must remain untouched.
    assert fs.read_text(target).endswith("# user-change\n")

    # Default copy must be available as *.bkkt.dist.
    dist_path = Path("/repo/__global/all.json.bkkt.dist")
    assert fs.exists(dist_path)
    assert fs.read_text(dist_path) == original


def test_repo_bootstrap_force_and_update_are_mutually_exclusive() -> None:
    fs = InMemoryFileSystem()
    ctx = SimpleNamespace(repo_root=Path("/repo"), fs=fs, logger=None)
    svc = RepoBootstrapService(ctx=ctx)

    args = Namespace(
        preset="full",
        only=None,
        init_templates_root=None,
        force=True,
        update=True,
        dry_run=False,
    )

    with pytest.raises(ConfigError):
        svc.run(args)
