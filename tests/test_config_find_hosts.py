from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from connectctl.app.context import CliContext
from connectctl.cli_parser import build_parser
from connectctl.services.config.find_service import ConfigFindService
import connectctl.services.config.hosts_service as hosts_service_module
from connectctl.services.config.hosts_service import ConfigHostsService
from connectctl.settings import Settings


def _make_ctx(repo_root: Path, cfg_path: Path) -> CliContext:
    settings = Settings.load(cfg_path, repo_root=repo_root)
    return CliContext(
        repo_root=repo_root,
        config_path=cfg_path,
        settings=settings,
        logger=logging.getLogger("test"),
    )


def _write_config(repo_root: Path) -> Path:
    cfg_path = repo_root / "connectctl.yaml"
    cfg_path.write_text(
        """
default_cluster: acme-main
clusters:
  acme-main:
    prod:
      connect:
        scheme: http
        port: 8083
        hosts: ["connect-a.local", "10.250.1.10"]
      kafka:
        bootstrap_servers: ["b-1.kafka.local:9098", "10.250.9.9:9098"]
      schema_registry:
        urls: ["http://schema-a.local:8081"]
  acme-external:
    prod:
      connect:
        scheme: http
        port: 8083
        hosts: ["connect-b.local"]
      render:
        prune_config_keys: ["bootstrap.servers", "*.schema.registry.url"]
""",
        encoding="utf-8",
    )
    return cfg_path


def _find_args(**overrides) -> argparse.Namespace:
    defaults = {
        "output": "json",
        "json": False,
        "cluster_group": None,
        "env": None,
        "connect_host": None,
        "kafka_bootstrap": None,
        "schema_registry_url": None,
        "connector": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _hosts_args(**overrides) -> argparse.Namespace:
    defaults = {
        "output": "json",
        "json": False,
        "cluster_group": ["acme-main"],
        "env": ["prod"],
        "connect_host": None,
        "dry_run": True,
        "yes": False,
        "timeout_seconds": 1.0,
        "skip_health_check": True,
        "jobs": 1,
        "rate_limit_per_second": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_config_find_matches_connect_host_and_runtime_endpoints(
    tmp_path: Path, capsys
) -> None:
    ctx = _make_ctx(tmp_path, _write_config(tmp_path))

    rc = ConfigFindService(ctx=ctx, logger=ctx.logger).run(
        _find_args(
            connect_host=["10.250.1.10"],
            kafka_bootstrap=["b-1.kafka.local:9098"],
            schema_registry_url=["schema-a.local"],
        )
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["match_count"] == 1
    match = payload["matches"][0]
    assert match["cluster_group"] == "acme-main"
    assert match["env"] == "prod"
    assert "connect-host" in match["matched_by"]
    assert "kafka-bootstrap" in match["matched_by"]
    assert "schema-registry" in match["matched_by"]
    assert match["kafka_bootstrap_source"] == "cluster config"
    assert match["schema_registry_source"] == "cluster config"


def test_config_hosts_add_dry_run_does_not_mutate_connectctl(
    tmp_path: Path, capsys
) -> None:
    cfg_path = _write_config(tmp_path)
    before = cfg_path.read_text(encoding="utf-8")
    ctx = _make_ctx(tmp_path, cfg_path)

    rc = ConfigHostsService(ctx=ctx, logger=ctx.logger).add(
        _hosts_args(connect_host=["connect-c.local"])
    )

    assert rc == 0
    assert cfg_path.read_text(encoding="utf-8") == before
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["planned_hosts"] == ["connect-c.local"]
    assert payload["operation"] == "add"
    assert payload["changed"] is True


def test_config_hosts_add_yes_preserves_yaml_comments_and_order(
    tmp_path: Path, capsys
) -> None:
    cfg_path = tmp_path / "connectctl.yaml"
    cfg_path.write_text(
        """# root comment
default_cluster: acme-main
clusters:
  # main cluster comment
  acme-main:
    prod:
      connect:
        # keep worker order and this comment
        scheme: http
        port: 8083
        hosts:
          - connect-a.local
      kafka:
        bootstrap_servers: ["b-1.kafka.local:9098"]
""",
        encoding="utf-8",
    )
    ctx = _make_ctx(tmp_path, cfg_path)

    rc = ConfigHostsService(ctx=ctx, logger=ctx.logger).add(
        _hosts_args(connect_host=["connect-b.local"], dry_run=False, yes=True)
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["changed"] is True
    text = cfg_path.read_text(encoding="utf-8")
    assert "# root comment" in text
    assert "# main cluster comment" in text
    assert "# keep worker order and this comment" in text
    assert text.index("default_cluster:") < text.index("clusters:")
    assert text.index("- connect-a.local") < text.index("- connect-b.local")


def test_config_hosts_check_filters_explicit_connect_host(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    cfg_path = _write_config(tmp_path)
    ctx = _make_ctx(tmp_path, cfg_path)
    checked_urls: list[str] = []

    def fake_check(url: str, *, timeout_seconds: float) -> Any:
        checked_urls.append(url)
        return hosts_service_module._HealthCheck(url=url, ok=True, status="200")

    monkeypatch.setattr(hosts_service_module, "_check_url", fake_check)

    rc = ConfigHostsService(ctx=ctx, logger=ctx.logger).check(
        _hosts_args(connect_host=["10.250.1.10"], dry_run=False)
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert checked_urls == ["http://10.250.1.10:8083"]
    assert payload["checked_count"] == 1


def test_config_hosts_parser_uses_connect_host_primary_and_host_alias() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "config",
            "hosts",
            "add",
            "--cluster",
            "acme-main",
            "--env",
            "prod",
            "--connect-host",
            "connect-a.local",
            "--host",
            "connect-b.local",
            "--dry-run",
        ]
    )

    assert args.config_cmd == "hosts"
    assert args.hosts_cmd == "add"
    assert args.cluster_group == ["acme-main"]
    assert args.connect_host == ["connect-a.local", "connect-b.local"]
    assert args.dry_run is True


def test_config_find_parser_uses_endpoint_specific_flags() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "config",
            "find",
            "--connect-host",
            "connect-a.local",
            "--kafka-bootstrap",
            "b-1.kafka.local:9098",
            "--schema-registry-url",
            "http://schema-a.local:8081",
            "--cluster",
            "acme-main",
            "--env",
            "prod",
        ]
    )

    assert args.config_cmd == "find"
    assert args.connect_host == ["connect-a.local"]
    assert args.kafka_bootstrap == ["b-1.kafka.local:9098"]
    assert args.schema_registry_url == ["http://schema-a.local:8081"]


def test_search_parser_keeps_db_host_and_runtime_endpoint_filters_separate() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "search",
            "--host",
            "source-db.local",
            "--kafka-bootstrap",
            "b-1.kafka.local:9098",
            "--schema-registry-url",
            "http://schema-a.local:8081",
        ]
    )

    assert args.host == ["source-db.local"]
    assert args.kafka_bootstrap == ["b-1.kafka.local:9098"]
    assert args.schema_registry_url == ["http://schema-a.local:8081"]
