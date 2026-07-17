from __future__ import annotations

import argparse
import builtins
import logging
from pathlib import Path

import yaml

from connectctl.app.context import CliContext
from connectctl.services.config.render_service import ConfigRenderService
from connectctl.settings import Settings


def _make_ctx(repo_root: Path, cfg_path: Path) -> CliContext:
    settings = Settings.load(cfg_path, repo_root=repo_root)
    return CliContext(
        repo_root=repo_root,
        config_path=cfg_path,
        settings=settings,
        logger=logging.getLogger("test"),
    )


def test_config_render_resolves_inheritance_and_masks_secrets(tmp_path: Path, capsys):
    repo_root = tmp_path
    cfg_path = repo_root / "connectctl.yaml"

    cfg_path.write_text(
        """
clusters:
  acme-main:
    dev:
      connect:
        scheme: http
        port: 8083
        hosts: ["10.0.0.1"]
      kafka:
        bootstrap_servers: ["b1:9092"]
        auth:
          type: sasl
          username: user
          password: secret123
    prod:
      connect:
        scheme: http
        port: 8084
        hosts: ["10.0.0.2"]

  acme-source:
    dev: from_cluster_group_env(acme-main, 'all')
    prod:
      connect:
        scheme: http
        port: from_cluster_group_env(acme-main, 'connect.port')
        hosts: ["10.1.1.1"]
""",
        encoding="utf-8",
    )

    ctx = _make_ctx(repo_root, cfg_path)
    svc = ConfigRenderService(ctx=ctx, logger=ctx.logger)

    args = argparse.Namespace(
        output="text",
        json=False,
        cluster_group=None,
        env=None,
        show_secrets=False,
        output_file=None,
    )

    rc = svc.run(args)
    assert rc == 0

    out = capsys.readouterr().out
    assert "from_cluster_group_env" not in out
    data = yaml.safe_load(out)

    assert data["clusters"]["acme-source"]["dev"]["connect"]["port"] == 8083
    assert data["clusters"]["acme-source"]["prod"]["connect"]["port"] == 8084

    # secret must be masked by default
    assert data["clusters"]["acme-main"]["dev"]["kafka"]["auth"]["password"] == "***"


def test_config_render_show_secrets(tmp_path: Path, capsys):
    repo_root = tmp_path
    cfg_path = repo_root / "connectctl.yaml"

    cfg_path.write_text(
        """
clusters:
  acme-main:
    dev:
      connect:
        scheme: http
        port: 8083
        hosts: ["10.0.0.1"]
      kafka:
        bootstrap_servers: ["b1:9092"]
        auth:
          type: sasl
          username: user
          password: secret123
""",
        encoding="utf-8",
    )

    ctx = _make_ctx(repo_root, cfg_path)
    svc = ConfigRenderService(ctx=ctx, logger=ctx.logger)

    args = argparse.Namespace(
        output="text",
        json=False,
        cluster_group=None,
        env=None,
        show_secrets=True,
        output_file=None,
    )

    rc = svc.run(args)
    assert rc == 0

    out = capsys.readouterr().out
    data = yaml.safe_load(out)
    assert (
        data["clusters"]["acme-main"]["dev"]["kafka"]["auth"]["password"] == "secret123"
    )


def test_config_render_prompts_for_broad_text_render(
    tmp_path: Path, capsys, monkeypatch
):
    repo_root = tmp_path
    cfg_path = repo_root / "connectctl.yaml"

    cfg_path.write_text(
        """
clusters:
  acme-main:
    dev:
      connect:
        scheme: http
        port: 8083
        hosts: ["10.0.0.1"]
""",
        encoding="utf-8",
    )

    ctx = _make_ctx(repo_root, cfg_path)
    svc = ConfigRenderService(ctx=ctx, logger=ctx.logger)

    monkeypatch.setattr(
        "connectctl.cli_helpers.default_scope_ux.is_interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(builtins, "input", lambda prompt: "n")

    args = argparse.Namespace(
        output="text",
        json=False,
        cluster_group=None,
        env=None,
        show_secrets=False,
        output_file=None,
        yes=False,
    )

    rc = svc.run(args)
    assert rc == 1
    assert capsys.readouterr().out == ""
