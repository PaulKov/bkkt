from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from connectctl.app.context import CliContext
from connectctl.cli_parser import build_parser
from connectctl.models import Environment
from connectctl.services.config.clusters_service import ConfigClustersService
from connectctl.settings import Settings


def _make_ctx(repo_root: Path, cfg_path: Path) -> CliContext:
    settings = Settings.load(cfg_path, repo_root=repo_root)
    return CliContext(
        repo_root=repo_root,
        config_path=cfg_path,
        settings=settings,
        logger=logging.getLogger("test"),
    )


def _args(**overrides) -> argparse.Namespace:
    defaults = {
        "output": "text",
        "json": False,
        "cluster_group": None,
        "env": None,
        "show_render_vars": False,
        "hide_kafka_bootstrap": False,
        "hide_schema_registry": False,
        "no_provenance": False,
        "view": "long",
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _write_config(repo_root: Path) -> Path:
    cfg_path = repo_root / "connectctl.yaml"
    cfg_path.write_text(
        """
default_cluster: cluster-a
clusters:
  cluster-a:
    dev:
      connect:
        scheme: http
        port: 8083
        hosts: ["connect-dev-a"]
      kafka:
        bootstrap_servers: ["kafka-dev-a:9092"]
    prod:
      connect:
        scheme: https
        port: 8443
        hosts: ["connect-prod-a", "connect-prod-b"]
      kafka:
        bootstrap_servers: ["kafka-prod-a:9098", "kafka-prod-b:9098"]
        auth:
          type: iam
          region: eu-west-1
      schema_registry:
        urls: ["http://schema-registry-a:8081", "http://schema-registry-b:8081"]
      render:
        prune_config_keys: ["bootstrap.servers"]
        vars:
          public_topic_prefix: prod
          registry_password: super-secret

  cluster-b:
    prod:
      connect:
        scheme: http
        port: 8083
        hosts: ["connect-prod-c"]
      kafka:
        bootstrap_servers: "kafka-prod-c:9092"
""",
        encoding="utf-8",
    )
    return cfg_path


def test_config_clusters_lists_inventory_as_text(tmp_path: Path, capsys) -> None:
    ctx = _make_ctx(tmp_path, _write_config(tmp_path))
    svc = ConfigClustersService(ctx=ctx, logger=ctx.logger)

    rc = svc.run(_args(env=["prod"]))

    assert rc == 0
    out = capsys.readouterr().out
    assert "default_cluster: `cluster-a`" in out
    assert "cluster-a" in out
    assert "cluster-b" in out
    assert "<br>" not in out
    assert "connect-prod-a:8443" in out
    assert "connect-prod-b:8443" in out
    assert "https://connect-prod-a:8443" in out
    assert "kafka-prod-a:9098" in out
    assert "kafka-prod-b:9098" in out
    assert "┌" in out
    assert "│" in out
    assert "`dev`" not in out


def test_config_clusters_uses_global_kafka_vars_as_inventory_fallback(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    monkeypatch.delenv("KAFKA_PROD_BOOTSTRAP_SERVERS", raising=False)
    monkeypatch.delenv("SCHEMA_REGISTRY_PROD_URL", raising=False)
    cfg_path = tmp_path / "connectctl.yaml"
    cfg_path.write_text(
        """
default_cluster: acme-main
clusters:
  acme-main:
    prod:
      connect:
        scheme: http
        port: 8083
        hosts: ["connect-prod-a"]
      kafka:
        bootstrap_servers: ${KAFKA_PROD_BOOTSTRAP_SERVERS:-}
        auth:
          type: iam
          region: eu-central-1
  acme-external:
    prod:
      connect:
        scheme: http
        port: 8083
        hosts: ["connect-external-a"]
      render:
        prune_config_keys:
          - "bootstrap.servers"
          - "*.schema.registry.url"
""",
        encoding="utf-8",
    )
    global_dir = tmp_path / "__global"
    global_dir.mkdir()
    (global_dir / "prod.json").write_text(
        json.dumps(
            {
                "vars": {
                    "kafka": {
                        "bootstrap_servers": "${KAFKA_PROD_BOOTSTRAP_SERVERS:-b-1.prod:9098,b-2.prod:9098}",
                        "schema_registry_url": "${SCHEMA_REGISTRY_PROD_URL:-http://sr-a:8081,http://sr-b:8081}",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    ctx = _make_ctx(tmp_path, cfg_path)
    svc = ConfigClustersService(ctx=ctx, logger=ctx.logger)

    rc = svc.run(_args(env=["prod"]))

    assert rc == 0
    out = capsys.readouterr().out
    assert "b-1.prod:9098" in out
    assert "b-2.prod:9098" in out
    assert "http://sr-a:8081" in out
    assert "http://sr-b:8081" in out
    assert "__global/prod.json vars" in out
    assert "worker-managed" in out
    assert "pruned by cluster render rules" in out
    assert "## Notes" in out


def test_config_clusters_filters_cluster_group_and_outputs_json(
    tmp_path: Path, capsys
) -> None:
    ctx = _make_ctx(tmp_path, _write_config(tmp_path))
    svc = ConfigClustersService(ctx=ctx, logger=ctx.logger)

    rc = svc.run(_args(output="json", cluster_group=["cluster-b"], env=["prod"]))

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["default_cluster"] == "cluster-a"
    assert payload["cluster_count"] == 1
    assert payload["env_scope_count"] == 1
    assert payload["clusters"][0]["name"] == "cluster-b"
    assert payload["clusters"][0]["is_default"] is False
    env_payload = payload["clusters"][0]["envs"][0]
    assert env_payload["env"] == "prod"
    assert env_payload["connect_hosts"] == ["connect-prod-c:8083"]
    assert env_payload["kafka_bootstrap_servers"] == ["kafka-prod-c:9092"]
    assert env_payload["kafka_hosts"] == ["kafka-prod-c"]
    assert env_payload["schema_registry_urls"] == []


def test_config_clusters_exposes_lifecycle_metadata(tmp_path: Path, capsys) -> None:
    cfg_path = tmp_path / "connectctl.yaml"
    cfg_path.write_text(
        """
default_cluster: acme-main
clusters:
  acme-main:
    dev:
      lifecycle:
        disabled: true
        reason: dev worker intentionally stopped
        ticket: DATAPLAT-2652
        until: explicit Data Platform owner re-enable
      connect:
        scheme: http
        port: 8083
        hosts: ["connect-dev-main"]
""",
        encoding="utf-8",
    )
    ctx = _make_ctx(tmp_path, cfg_path)
    svc = ConfigClustersService(ctx=ctx, logger=ctx.logger)

    rc = svc.run(_args(output="json", cluster_group=["acme-main"], env=["dev"]))

    assert rc == 0
    env_payload = json.loads(capsys.readouterr().out)["clusters"][0]["envs"][0]
    assert env_payload["lifecycle"] == {
        "disabled": True,
        "status": "disabled",
        "reason": "dev worker intentionally stopped",
        "ticket": "DATAPLAT-2652",
        "until": "explicit Data Platform owner re-enable",
    }

    rc = svc.run(_args(cluster_group=["acme-main"], env=["dev"]))

    assert rc == 0
    out = capsys.readouterr().out
    assert "disabled" in out
    assert "DATAPLAT-2652" in out
    assert "dev worker intentionally stopped" in out


def test_config_clusters_can_include_masked_render_vars(tmp_path: Path, capsys) -> None:
    ctx = _make_ctx(tmp_path, _write_config(tmp_path))
    svc = ConfigClustersService(ctx=ctx, logger=ctx.logger)

    rc = svc.run(
        _args(
            output="json",
            cluster_group=["cluster-a"],
            env=["prod"],
            show_render_vars=True,
        )
    )

    assert rc == 0
    env_payload = json.loads(capsys.readouterr().out)["clusters"][0]["envs"][0]
    assert env_payload["render_prune_config_keys"] == ["bootstrap.servers"]
    assert env_payload["render_vars"]["public_topic_prefix"] == "prod"
    assert env_payload["render_vars"]["registry_password"] == "***"
    assert env_payload["kafka_auth"] == {
        "security_protocol": "SASL_SSL",
        "sasl_mechanism": "OAUTHBEARER",
        "iam_region": "eu-west-1",
    }
    assert env_payload["schema_registry_urls"] == [
        "http://schema-registry-a:8081",
        "http://schema-registry-b:8081",
    ]
    schema_registry = ctx.settings.cluster_groups["cluster-a"][
        Environment.prod
    ].schema_registry
    assert schema_registry is not None
    assert schema_registry.urls == (
        "http://schema-registry-a:8081",
        "http://schema-registry-b:8081",
    )


def test_config_clusters_parser_accepts_cluster_alias() -> None:
    parser = build_parser()

    args = parser.parse_args(
        ["config", "clusters", "--cluster", "cluster-a", "--env", "prod"]
    )

    assert args.config_cmd == "clusters"
    assert args.cluster_group == ["cluster-a"]
    assert "--cluster" in args._explicit_options


def test_config_clusters_can_hide_runtime_columns_and_provenance(
    tmp_path: Path, capsys
) -> None:
    ctx = _make_ctx(tmp_path, _write_config(tmp_path))
    svc = ConfigClustersService(ctx=ctx, logger=ctx.logger)

    rc = svc.run(
        _args(
            env=["prod"],
            hide_kafka_bootstrap=True,
            hide_schema_registry=True,
            no_provenance=True,
        )
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "Kafka bootstrap" not in out
    assert "Schema Registry" not in out
    assert "## Notes" not in out
    assert "connect-prod-a:8443" in out


def test_config_clusters_short_view_keeps_table_compact(tmp_path: Path, capsys) -> None:
    ctx = _make_ctx(tmp_path, _write_config(tmp_path))
    svc = ConfigClustersService(ctx=ctx, logger=ctx.logger)

    rc = svc.run(_args(env=["prod"], view="short"))

    assert rc == 0
    out = capsys.readouterr().out
    assert "Connect URLs" not in out
    assert "Connect hosts" in out
    assert "Kafka bootstrap" in out
