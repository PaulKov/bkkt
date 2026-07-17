from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pytest

from connectctl.app.context import CliContext
from connectctl.cli_parser import build_parser
from connectctl.exceptions import ConfigError
from connectctl.models import Environment
from connectctl.services.config.clusters_service import ConfigClustersService
from connectctl.services.config.hosts_service import ConfigHostsService
from connectctl.services.config.runtimes_service import ConfigRuntimesService
from connectctl.settings import Settings


def _make_ctx(repo_root: Path, cfg_path: Path) -> CliContext:
    settings = Settings.load(cfg_path, repo_root=repo_root)
    return CliContext(
        repo_root=repo_root,
        config_path=cfg_path,
        settings=settings,
        logger=logging.getLogger("test"),
    )


def _clusters_args(**overrides) -> argparse.Namespace:
    defaults = {
        "output": "json",
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


def _hosts_args(**overrides) -> argparse.Namespace:
    defaults = {
        "output": "json",
        "json": False,
        "cluster_group": ["acme-main_k8s"],
        "env": ["prod"],
        "connect_host": ["connect-b.local"],
        "dry_run": False,
        "yes": True,
        "timeout_seconds": 1.0,
        "skip_health_check": True,
        "jobs": 1,
        "rate_limit_per_second": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _runtimes_args(**overrides) -> argparse.Namespace:
    defaults = {
        "output": "json",
        "json": False,
        "cluster_group": None,
        "env": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _write_runtime_config(repo_root: Path) -> Path:
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
        hosts: ["connect-prod-a", "connect-prod-b"]
      kafka:
        bootstrap_servers: ["b-1.kafka.local:9098"]

  acme-main_k8s:
    prod:
      connect:
        runtime:
          type: strimzi
          kubernetes:
            context: prod-eks
            namespace: kafka-connect
          strimzi:
            kafka_connect_name: acme-main-connect
            connector_label_selector: strimzi.io/cluster=acme-main-connect
          rest:
            access: port_forward
            service: acme-main-connect-api
            port: 8083
            local_port: 18083
      kafka:
        bootstrap_servers: from_cluster_group_env(acme-main, 'kafka.bootstrap_servers')

  acme-managed:
    prod:
      connect:
        runtime:
          type: managed_connect
          provider: aws_msk_connect
          name: prod-msk-connect
""",
        encoding="utf-8",
    )
    return cfg_path


def test_legacy_connect_hosts_parse_as_static_runtime(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, _write_runtime_config(tmp_path))
    cluster = ctx.settings.cluster_groups["acme-main"][Environment.prod]

    assert cluster.runtime.type == "static_hosts"
    assert cluster.runtime.operator_managed is False
    assert cluster.runtime.mutation_mode == "rest"
    assert cluster.runtime.rest_access == "direct"
    assert cluster.runtime.limitations == ()
    assert cluster.urls == [
        "http://connect-prod-a:8083",
        "http://connect-prod-b:8083",
    ]


def test_strimzi_runtime_parse_and_exposes_operator_metadata(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, _write_runtime_config(tmp_path))
    cluster = ctx.settings.cluster_groups["acme-main_k8s"][Environment.prod]

    assert cluster.runtime.type == "strimzi"
    assert cluster.runtime.operator_managed is True
    assert cluster.runtime.mutation_mode == "crd"
    assert cluster.runtime.rest_access == "port_forward"
    assert cluster.runtime.kubernetes_context == "prod-eks"
    assert cluster.runtime.kubernetes_namespace == "kafka-connect"
    assert cluster.runtime.service == "acme-main-connect-api"
    assert cluster.runtime.port == 8083
    assert cluster.runtime.local_port == 18083
    assert cluster.runtime.resource_name == "acme-main-connect"
    assert cluster.runtime.connector_label_selector == (
        "strimzi.io/cluster=acme-main-connect"
    )
    assert cluster.urls == ("http://127.0.0.1:18083",)


def test_config_clusters_json_and_text_include_runtime_metadata(
    tmp_path: Path, capsys
) -> None:
    ctx = _make_ctx(tmp_path, _write_runtime_config(tmp_path))
    svc = ConfigClustersService(ctx=ctx, logger=ctx.logger)

    rc = svc.run(
        _clusters_args(
            cluster_group=["acme-main_k8s"],
            env=["prod"],
            output="json",
        )
    )

    assert rc == 0
    env_payload = json.loads(capsys.readouterr().out)["clusters"][0]["envs"][0]
    assert env_payload["runtime"] == {
        "type": "strimzi",
        "operator_managed": True,
        "mutation_mode": "crd",
        "rest_access": "port_forward",
        "kubernetes_context": "prod-eks",
        "kubernetes_namespace": "kafka-connect",
        "service": "acme-main-connect-api",
        "pod_selector": None,
        "resource_name": "acme-main-connect",
        "connector_label_selector": "strimzi.io/cluster=acme-main-connect",
        "provider": None,
        "limitations": [
            "REST mutations are disabled by default; mutate KafkaConnector CRDs.",
        ],
    }

    rc = svc.run(
        _clusters_args(
            cluster_group=["acme-main_k8s"],
            env=["prod"],
            output="text",
            view="details",
        )
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "Runtime" in out
    assert "strimzi" in out
    assert "prod-eks" in out
    assert "kafka-connect" in out
    assert "acme-main-connect-api" in out
    assert "operator-managed" in out


def test_config_hosts_add_rejects_operator_managed_runtime(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(tmp_path, _write_runtime_config(tmp_path))

    with pytest.raises(ConfigError, match="static_hosts"):
        ConfigHostsService(ctx=ctx, logger=ctx.logger).add(_hosts_args())


def test_runtime_guard_blocks_rest_mutation_without_break_glass(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(tmp_path, _write_runtime_config(tmp_path))

    with pytest.raises(ConfigError, match="runtime-unsafe-rest"):
        ctx.assert_rest_mutation_allowed(
            Environment.prod,
            "acme-main_k8s",
            command="apply",
            unsafe=False,
        )

    ctx.assert_rest_mutation_allowed(
        Environment.prod,
        "acme-main_k8s",
        command="apply",
        unsafe=True,
    )
    ctx.assert_rest_mutation_allowed(
        Environment.prod,
        "acme-main",
        command="apply",
        unsafe=False,
    )


def test_config_runtimes_list_explain_check_and_parser(tmp_path: Path, capsys) -> None:
    ctx = _make_ctx(tmp_path, _write_runtime_config(tmp_path))
    svc = ConfigRuntimesService(ctx=ctx, logger=ctx.logger)

    rc = svc.list(_runtimes_args(output="json", cluster_group=["acme-main_k8s"]))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["runtime_count"] == 1
    assert payload["runtimes"][0]["runtime"]["type"] == "strimzi"

    rc = svc.explain(_runtimes_args(output="json", cluster_group=["acme-managed"]))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["runtime"]["type"] == "managed_connect"
    assert payload["runtime"]["mutation_mode"] == "read_only"

    rc = svc.check(_runtimes_args(output="json"))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    statuses = {
        (item["cluster_group"], item["env"]): item["status"]
        for item in payload["checks"]
    }
    assert statuses[("acme-main", "prod")] == "ok"
    assert statuses[("acme-main_k8s", "prod")] == "limited"
    assert statuses[("acme-managed", "prod")] == "limited"

    parser = build_parser()
    args = parser.parse_args(
        ["config", "runtimes", "check", "--cluster", "acme-main_k8s", "--env", "prod"]
    )
    assert args.config_cmd == "runtimes"
    assert args.runtimes_cmd == "check"
    assert args.cluster_group == ["acme-main_k8s"]
    assert args.env == ["prod"]


def test_connect_runtime_inventory_parsers_are_registered() -> None:
    parser = build_parser()

    workers = parser.parse_args(
        ["connect", "workers", "inventory", "--env", "prod", "--cluster", "acme-main"]
    )
    assert workers.connect_cmd == "workers"
    assert workers.workers_cmd == "inventory"
    assert workers.cluster == "acme-main"

    plugins = parser.parse_args(
        ["connect", "plugins", "inventory", "--env", "prod", "--cluster", "acme-main"]
    )
    assert plugins.connect_cmd == "plugins"
    assert plugins.plugins_cmd == "inventory"

    runtime = parser.parse_args(
        ["connect", "runtime", "diff", "--env", "prod", "--cluster", "acme-main"]
    )
    assert runtime.connect_cmd == "runtime"
    assert runtime.runtime_cmd == "diff"
