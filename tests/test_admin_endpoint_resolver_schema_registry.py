from __future__ import annotations

import json
import logging
from argparse import Namespace
from pathlib import Path

from connectctl.app.context import CliContext
from connectctl.exceptions import ConfigError
from connectctl.models import SchemaRegistryConfig
from connectctl.services.schema_registry import SchemaRegistryService
from connectctl.settings import Settings


class _FallbackSchemaRegistry:
    def __init__(self, cfg: SchemaRegistryConfig) -> None:
        self.cfg = cfg

    def list_subjects(self, **kwargs):
        return ["orders-value"]


def _args(**overrides):
    base = {
        "env": "prod",
        "cluster": "acme-main",
        "output": "json",
        "output_file": None,
        "prefix": None,
        "regexp": None,
        "limit": 10,
        "url": None,
        "timeout": None,
    }
    base.update(overrides)
    return Namespace(**base)


def _settings_ctx(repo_root: Path, cfg_path: Path) -> CliContext:
    return CliContext(
        repo_root=repo_root,
        config_path=cfg_path,
        settings=Settings.load(cfg_path, repo_root=repo_root),
        logger=logging.getLogger("test"),
    )


def _write_schema_fallback_repo(repo_root: Path, *, prune: bool = False) -> Path:
    cfg_path = repo_root / "connectctl.yaml"
    prune_yaml = (
        """
      render:
        prune_config_keys:
          - "*.schema.registry.url"
"""
        if prune
        else ""
    )
    cfg_path.write_text(
        f"""
default_cluster: acme-main
clusters:
  acme-main:
    prod:
      connect:
        scheme: http
        port: 8083
        hosts: ["connect-prod"]
      schema_registry:
        urls: ${{SCHEMA_REGISTRY_PROD_URL:-}}
{prune_yaml}
""",
        encoding="utf-8",
    )
    global_dir = repo_root / "__global"
    global_dir.mkdir()
    (global_dir / "prod.json").write_text(
        json.dumps(
            {
                "vars": {
                    "kafka": {
                        "bootstrap_servers": "${KAFKA_PROD_BOOTSTRAP_SERVERS:-b-1.prod:9098}",
                        "schema_registry_url": "${SCHEMA_REGISTRY_PROD_URL:-http://sr-a:8081,http://sr-b:8081}",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return cfg_path


def test_subjects_list_resolves_schema_registry_from_global_vars(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    monkeypatch.delenv("SCHEMA_REGISTRY_PROD_URL", raising=False)
    cfg_path = _write_schema_fallback_repo(tmp_path)
    svc = SchemaRegistryService(
        ctx=_settings_ctx(tmp_path, cfg_path),
        client_factory=_FallbackSchemaRegistry,
    )

    rc = svc.run_subjects_list(_args())

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_registry_urls"] == [
        "http://sr-a:8081",
        "http://sr-b:8081",
    ]
    assert payload["schema_registry_source"] == "__global/prod.json vars"


def test_subjects_list_url_override_wins_over_cluster_and_repo_defaults(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    monkeypatch.delenv("SCHEMA_REGISTRY_PROD_URL", raising=False)
    cfg_path = _write_schema_fallback_repo(tmp_path)
    svc = SchemaRegistryService(
        ctx=_settings_ctx(tmp_path, cfg_path),
        client_factory=_FallbackSchemaRegistry,
    )

    rc = svc.run_subjects_list(_args(url="http://override-sr:8081"))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_registry_urls"] == ["http://override-sr:8081"]
    assert payload["schema_registry_source"] == "cli override"


def test_subjects_list_does_not_fallback_when_schema_registry_is_pruned(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("SCHEMA_REGISTRY_PROD_URL", raising=False)
    cfg_path = _write_schema_fallback_repo(tmp_path, prune=True)
    svc = SchemaRegistryService(
        ctx=_settings_ctx(tmp_path, cfg_path),
        client_factory=_FallbackSchemaRegistry,
    )

    try:
        svc.run_subjects_list(_args())
    except ConfigError as exc:
        text = str(exc)
        assert "pruned" in text
        assert "schema.registry.url" in text
    else:
        raise AssertionError("pruned Schema Registry config must not fallback")
