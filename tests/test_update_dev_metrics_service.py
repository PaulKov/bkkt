from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pytest

from connectctl.app.context import CliContext
from connectctl.services.docs.update_dev_metrics_service import (
    UpdateDevMetricsService,
)
from connectctl.settings import Settings


def _make_ctx(repo_root: Path) -> CliContext:
    cfg_path = repo_root / "connectctl.yaml"
    cfg_path.write_text(
        """
version: 1
connectors_root: connectors
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
    logger = logging.getLogger(f"test-update-dev-metrics-{repo_root.name}")
    logger.handlers = []
    logger.setLevel(logging.INFO)
    return CliContext(
        repo_root=repo_root,
        config_path=cfg_path,
        settings=settings,
        logger=logger,
    )


def _prepare_repo(tmp_path: Path) -> CliContext:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "ENGINEERING_METRICS.md").write_text(
        "# Engineering Metrics\n\n<!-- BKKT_DEV_METRICS_START -->\nstale\n<!-- BKKT_DEV_METRICS_END -->\n",
        encoding="utf-8",
    )

    connectctl_dir = tmp_path / "connectctl"
    connectctl_dir.mkdir(parents=True, exist_ok=True)
    (connectctl_dir / "__init__.py").write_text("", encoding="utf-8")
    (connectctl_dir / "sample.py").write_text(
        """
# comment-only line

VALUE = 1

def build() -> int:
    return VALUE
""",
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_sample.py").write_text(
        """
def test_smoke() -> None:
    assert True
""",
        encoding="utf-8",
    )
    return _make_ctx(tmp_path)


def test_update_dev_metrics_writes_engineering_metrics_docs(tmp_path: Path) -> None:
    ctx = _prepare_repo(tmp_path)
    svc = UpdateDevMetricsService(ctx=ctx, logger=ctx.logger)

    rc = svc.run(
        argparse.Namespace(
            docs_dir="docs",
            target="all",
            check=False,
            top=5,
        )
    )

    assert rc == 0

    md_text = (tmp_path / "docs" / "ENGINEERING_METRICS.md").read_text(encoding="utf-8")

    assert "Repository Python footprint" in md_text
    assert "Python files excluding tests" in md_text
    assert "`connectctl` package footprint" in md_text


def test_update_dev_metrics_check_reports_stale_docs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ctx = _prepare_repo(tmp_path)
    svc = UpdateDevMetricsService(ctx=ctx, logger=ctx.logger)

    with caplog.at_level(logging.INFO, logger=ctx.logger.name):
        rc = svc.run(
            argparse.Namespace(
                docs_dir="docs",
                target="md",
                check=True,
                top=5,
            )
        )

    assert rc == 2
    assert "Engineering metrics docs are out of date" in caplog.text
