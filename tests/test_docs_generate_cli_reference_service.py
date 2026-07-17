from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pytest

from connectctl.app.context import CliContext
from connectctl.services.docs.generate_cli_reference_service import (
    GenerateCliReferenceService,
)
from connectctl.settings import Settings


def _make_ctx(repo_root: Path) -> CliContext:
    cfg_path = repo_root / "connectctl.yaml"
    cfg_path.write_text(
        """
version: 1
connectors_root: .
default_cluster: acme-main
clusters:
  acme-main:
    dev:
      connect:
        scheme: http
        port: 8083
        hosts: ["127.0.0.1"]
""",
        encoding="utf-8",
    )
    settings = Settings.load(cfg_path, repo_root=repo_root)
    logger = logging.getLogger(f"test-docs-{repo_root.name}")
    logger.handlers = []
    logger.setLevel(logging.INFO)
    return CliContext(
        repo_root=repo_root,
        config_path=cfg_path,
        settings=settings,
        logger=logger,
    )


def test_generate_cli_reference_check_show_diff_outputs_unified_diff(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "CLI_REFERENCE.md").write_text("stale md\n", encoding="utf-8")

    ctx = _make_ctx(tmp_path)
    svc = GenerateCliReferenceService(ctx=ctx, logger=ctx.logger)

    args = argparse.Namespace(
        docs_dir="docs",
        target="all",
        check=True,
        show_diff=True,
        diff_lines=20,
    )

    with caplog.at_level(logging.INFO, logger=ctx.logger.name):
        rc = svc.run(args)
    assert rc == 2

    text = caplog.text
    assert "CLI reference diff for docs/CLI_REFERENCE.md" in text
    assert "--- current:docs/CLI_REFERENCE.md" in text
    assert "+++ generated:docs/CLI_REFERENCE.md" in text


def test_generate_cli_reference_check_without_diff_keeps_output_compact(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "CLI_REFERENCE.md").write_text("stale md\n", encoding="utf-8")

    ctx = _make_ctx(tmp_path)
    svc = GenerateCliReferenceService(ctx=ctx, logger=ctx.logger)

    args = argparse.Namespace(
        docs_dir="docs",
        target="all",
        check=True,
        show_diff=False,
        diff_lines=20,
    )

    with caplog.at_level(logging.INFO, logger=ctx.logger.name):
        rc = svc.run(args)
    assert rc == 2

    text = caplog.text
    assert "CLI reference docs устарели" in text
    assert "CLI reference diff for" not in text
