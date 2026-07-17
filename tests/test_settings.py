from pathlib import Path

import pytest

from connectctl.app.context import CliContext
from connectctl.exceptions import ConfigError
from connectctl.models import Environment
from connectctl.settings import Settings


def test_settings_load_urls(tmp_path: Path):
    repo_root = tmp_path
    cfg_path = repo_root / "connectctl.yaml"
    cfg_path.write_text(
        """
clusters:
  dev:
    connect:
      scheme: http
      port: 8083
      hosts: [\"10.0.0.1\"]
  prod:
    connect:
      scheme: http
      port: 8083
      hosts:
        - 10.0.0.2
        - 10.0.0.3
""",
        encoding="utf-8",
    )

    s = Settings.load(cfg_path, repo_root=repo_root)
    assert s.clusters[Environment.dev].urls == ["http://10.0.0.1:8083"]
    assert s.clusters[Environment.prod].urls == [
        "http://10.0.0.2:8083",
        "http://10.0.0.3:8083",
    ]


def test_settings_safety_defaults(tmp_path: Path):
    repo_root = tmp_path
    cfg_path = repo_root / "connectctl.yaml"
    cfg_path.write_text(
        """
clusters:
  dev:
    connect:
      scheme: http
      port: 8083
      hosts: ["10.0.0.1"]
""",
        encoding="utf-8",
    )

    s = Settings.load(cfg_path, repo_root=repo_root)
    # Default policy: enabled, dev-only, existing-only, creation disabled
    assert bool(s.safety.direct_put.enabled) is True
    assert list(s.safety.direct_put.allowed_envs) == ["dev"]
    assert bool(s.safety.direct_put.require_existing) is True
    assert bool(s.safety.direct_put.allow_create) is False


def test_settings_safety_override(tmp_path: Path):
    repo_root = tmp_path
    cfg_path = repo_root / "connectctl.yaml"
    cfg_path.write_text(
        """
clusters:
  dev:
    connect:
      scheme: http
      port: 8083
      hosts: ["10.0.0.1"]
safety:
  direct_put:
    enabled: true
    allowed_envs: ["dev", "stage"]
    require_existing: false
    allow_create: true
""",
        encoding="utf-8",
    )

    s = Settings.load(cfg_path, repo_root=repo_root)
    assert list(s.safety.direct_put.allowed_envs) == ["dev", "stage"]
    assert bool(s.safety.direct_put.require_existing) is False
    assert bool(s.safety.direct_put.allow_create) is True


def test_settings_cluster_render_vars_and_inheritance(tmp_path: Path):
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
      render:
        vars:
          server_id_namespace: acme-main-dev-v1
    prod:
      connect:
        scheme: http
        port: 8083
        hosts: ["10.0.0.2"]
      render:
        vars:
          server_id_namespace: acme-main-prod-v1

  acme-source:
    dev: from_cluster_group_env(acme-main, 'all')
    prod:
      connect:
        scheme: http
        port: from_cluster_group_env(acme-main, 'connect.port')
        hosts: ["10.1.1.1"]
      render:
        vars:
          server_id_namespace: acme-source-prod-v1
default_cluster: acme-main
""",
        encoding="utf-8",
    )

    s = Settings.load(cfg_path, repo_root=repo_root)
    assert s.cluster_groups["acme-main"][Environment.dev].render_vars == {
        "server_id_namespace": "acme-main-dev-v1"
    }
    assert s.cluster_groups["acme-source"][Environment.dev].render_vars == {
        "server_id_namespace": "acme-main-dev-v1"
    }
    assert s.cluster_groups["acme-source"][Environment.prod].render_vars == {
        "server_id_namespace": "acme-source-prod-v1"
    }


def test_settings_cluster_lifecycle_inherits_and_can_be_overridden(
    tmp_path: Path,
):
    repo_root = tmp_path
    cfg_path = repo_root / "connectctl.yaml"
    cfg_path.write_text(
        """
cluster_lifecycle:
  overrides:
    - cluster: acme-source
      env: dev
      disabled: true
      reason: alias scope intentionally inherits disabled source
      ticket: DATAPLAT-2652
clusters:
  acme-main:
    lifecycle:
      disabled: true
      reason: dev group intentionally stopped
      ticket: DATAPLAT-1
    dev:
      lifecycle:
        reason: dev worker intentionally stopped
        ticket: DATAPLAT-2
      connect:
        scheme: http
        port: 8083
        hosts: ["10.100.1.56"]
    prod:
      connect:
        scheme: http
        port: 8083
        hosts: ["10.250.1.54"]
  acme-source:
    dev: from_cluster_group_env(acme-main, 'all')
default_cluster: acme-main
""",
        encoding="utf-8",
    )

    s = Settings.load(cfg_path, repo_root=repo_root)

    main_dev = s.cluster_groups["acme-main"][Environment.dev]
    main_prod = s.cluster_groups["acme-main"][Environment.prod]
    source_dev = s.cluster_groups["acme-source"][Environment.dev]
    assert main_dev.lifecycle.disabled is True
    assert main_dev.lifecycle.reason == "dev worker intentionally stopped"
    assert main_dev.lifecycle.ticket == "DATAPLAT-2"
    assert main_prod.lifecycle.disabled is True
    assert main_prod.lifecycle.reason == "dev group intentionally stopped"
    assert source_dev.lifecycle.disabled is True
    assert (
        source_dev.lifecycle.reason
        == "alias scope intentionally inherits disabled source"
    )
    assert source_dev.lifecycle.ticket == "DATAPLAT-2652"


def test_disabled_lifecycle_requires_reason(tmp_path: Path):
    cfg_path = tmp_path / "connectctl.yaml"
    cfg_path.write_text(
        """
clusters:
  acme-main:
    dev:
      lifecycle:
        disabled: true
      connect:
        scheme: http
        port: 8083
        hosts: ["10.100.1.56"]
default_cluster: acme-main
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="lifecycle.reason is required"):
        Settings.load(cfg_path, repo_root=tmp_path)


def test_explicit_disabled_cluster_fast_fails_with_metadata(tmp_path: Path):
    cfg_path = tmp_path / "connectctl.yaml"
    cfg_path.write_text(
        """
clusters:
  acme-main:
    dev:
      lifecycle:
        disabled: true
        reason: dev worker intentionally stopped
        ticket: DATAPLAT-2652
      connect:
        scheme: http
        port: 8083
        hosts: ["10.100.1.56"]
default_cluster: acme-main
""",
        encoding="utf-8",
    )
    settings = Settings.load(cfg_path, repo_root=tmp_path)
    ctx = CliContext(
        repo_root=tmp_path,
        config_path=cfg_path,
        settings=settings,
        logger=None,
    )

    with pytest.raises(ConfigError, match="DATAPLAT-2652"):
        ctx.resolve_cluster(Environment.dev, "acme-main")
