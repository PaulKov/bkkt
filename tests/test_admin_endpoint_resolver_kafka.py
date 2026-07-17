from __future__ import annotations

import json
import logging
from argparse import Namespace
from pathlib import Path

from connectctl.app.context import CliContext
from connectctl.exceptions import ConfigError
from connectctl.kafka.admin import (
    KafkaConsumerGroupDescription,
    KafkaConsumerGroupSummary,
    KafkaConsumerGroupTopicLag,
)
from connectctl.models import KafkaConfig
from connectctl.services.kafka_admin import KafkaAdminService
from connectctl.settings import Settings


class _FallbackKafkaAdmin:
    def __init__(self, cfg: KafkaConfig) -> None:
        self.cfg = cfg

    def describe_consumer_group(self, group_id, *, topics=()):
        return KafkaConsumerGroupDescription(
            summary=KafkaConsumerGroupSummary(
                group_id=group_id,
                protocol_type="consumer",
                state="Stable",
                members=1,
            ),
            topics=(
                KafkaConsumerGroupTopicLag(
                    topic=topics[0] if topics else "orders",
                    partitions=1,
                    committed_sum=3,
                    end_offset_sum=10,
                    lag_sum=7,
                ),
            ),
        )


def _args(**overrides):
    base = {
        "env": "prod",
        "cluster": "acme-main",
        "group": "connect-orders",
        "topic": "orders",
        "output": "json",
        "output_file": None,
        "bootstrap_server": None,
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


def _write_admin_fallback_repo(
    repo_root: Path,
    *,
    cluster_bootstrap: str = "${KAFKA_PROD_BOOTSTRAP_SERVERS:-}",
    prune: bool = False,
) -> Path:
    cfg_path = repo_root / "connectctl.yaml"
    prune_yaml = (
        """
      render:
        prune_config_keys:
          - "bootstrap.servers"
          - "*override.bootstrap.servers"
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
      kafka:
        bootstrap_servers: {cluster_bootstrap}
        auth:
          type: iam
          region: eu-central-1
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
                        "bootstrap_servers": "${KAFKA_PROD_BOOTSTRAP_SERVERS:-b-1.prod:9098,b-2.prod:9098}",
                        "schema_registry_url": "${SCHEMA_REGISTRY_PROD_URL:-http://sr-a:8081}",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return cfg_path


def test_group_lag_resolves_bootstrap_from_global_vars_when_cluster_env_is_empty(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    monkeypatch.delenv("KAFKA_PROD_BOOTSTRAP_SERVERS", raising=False)
    cfg_path = _write_admin_fallback_repo(tmp_path)
    svc = KafkaAdminService(
        ctx=_settings_ctx(tmp_path, cfg_path),
        client_factory=_FallbackKafkaAdmin,
    )

    rc = svc.run_groups_lag(_args())

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["group"]["topics"][0]["lag_sum"] == 7
    assert payload["bootstrap_servers"] == ["b-1.prod:9098", "b-2.prod:9098"]
    assert payload["bootstrap_source"] == "__global/prod.json vars"


def test_group_lag_keeps_explicit_cluster_bootstrap_before_repo_defaults(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    monkeypatch.delenv("KAFKA_PROD_BOOTSTRAP_SERVERS", raising=False)
    cfg_path = _write_admin_fallback_repo(
        tmp_path,
        cluster_bootstrap='["broker-explicit:9098"]',
    )
    svc = KafkaAdminService(
        ctx=_settings_ctx(tmp_path, cfg_path),
        client_factory=_FallbackKafkaAdmin,
    )

    rc = svc.run_groups_lag(_args())

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["bootstrap_servers"] == ["broker-explicit:9098"]
    assert payload["bootstrap_source"] == "cluster config"


def test_group_lag_does_not_fallback_when_bootstrap_is_worker_managed(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("KAFKA_PROD_BOOTSTRAP_SERVERS", raising=False)
    cfg_path = _write_admin_fallback_repo(tmp_path, prune=True)
    svc = KafkaAdminService(
        ctx=_settings_ctx(tmp_path, cfg_path),
        client_factory=_FallbackKafkaAdmin,
    )

    try:
        svc.run_groups_lag(_args())
    except ConfigError as exc:
        text = str(exc)
        assert "worker-managed" in text
        assert "bootstrap.servers" in text
    else:
        raise AssertionError("worker-managed Kafka bootstrap must not fallback")
