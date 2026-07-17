from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, Optional, Sequence

from connectctl.models import ConnectClusterConfig, ConnectorStatus, Environment


@dataclass
class _DummyCtx:
    """Минимальный CLI context для smoke-тестов команд.

    Нам важно проверить, что команды исполняются без runtime ошибок
    (в том числе с OutputFormat и парсингом аргументов), не требуя
    реального Kafka Connect.
    """

    cluster: ConnectClusterConfig
    client: Any
    logger: logging.Logger

    def resolve_cluster(
        self, env: Environment, cluster_override: Optional[str]
    ) -> ConnectClusterConfig:
        return self.cluster

    def connect_client(
        self, env: Environment, cluster_override: Optional[str], *, throttle=None
    ) -> Any:
        return self.client


class _FakeConnect:
    base_urls: Sequence[str] = ("http://dummy:8083",)

    def __init__(self) -> None:
        self._configs: Dict[str, Dict[str, Any]] = {
            "dev.payments.orders.source.postgres.cdc.0": {"name": "demo"},
            "dev.payments.users.sink.raw.iceberg.cdc.events.1": {"name": "demo2"},
        }

    def list_connectors(self) -> Sequence[str]:
        return list(self._configs.keys())

    def get_status(self, name: str) -> ConnectorStatus:
        return ConnectorStatus(
            name=name,
            connector_state="RUNNING",
            worker_id="worker-1",
            task_states=("RUNNING", "RUNNING"),
            raw={},
        )

    def get_config_optional(self, name: str) -> Optional[Dict[str, Any]]:
        return self._configs.get(name)

    def list_endpoint_diagnostics(self, *, name: str | None = None) -> Sequence[Any]:
        attempt = SimpleNamespace(
            base_url="http://dummy:8083",
            method="GET",
            path="/connectors",
            status_code=200,
            elapsed_ms=1.0,
            error=None,
            response_preview=None,
            transient=False,
            to_dict=lambda: {
                "base_url": "http://dummy:8083",
                "method": "GET",
                "path": "/connectors",
                "status_code": 200,
                "elapsed_ms": 1.0,
                "transient": False,
            },
        )
        return [
            SimpleNamespace(
                base_url="http://dummy:8083",
                healthy=True,
                checks=[attempt],
                to_dict=lambda: {
                    "base_url": "http://dummy:8083",
                    "healthy": True,
                    "checks": [attempt.to_dict()],
                },
            )
        ]

    def get_offsets(self, name: str) -> Dict[str, Any]:
        return {"offsets": [{"partition": {"connector": name}, "offset": {"pos": 1}}]}

    def patch_offsets(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"patched": name, "entries": len(payload.get("offsets", []))}


def _logger() -> logging.Logger:
    log = logging.getLogger("bkkt-tests")
    # Avoid duplicate handlers in repeated runs
    if not any(isinstance(h, logging.NullHandler) for h in log.handlers):
        log.addHandler(logging.NullHandler())
    return log


def test_get_connector_text_smoke() -> None:
    """Команда `bkkt get-connector` не должна падать в text-режиме."""

    from connectctl.commands.get_connector_cmd import cmd_get_connector

    client = _FakeConnect()
    cluster = ConnectClusterConfig(
        env=Environment.dev, urls=list(client.base_urls), name="acme-external"
    )
    ctx = _DummyCtx(cluster=cluster, client=client, logger=_logger())

    args = argparse.Namespace(
        env="dev",
        cluster="acme-external",
        name="dev.payments.orders.source.postgres.cdc.0",
        status="short",
        meta=True,
        output="text",
        json=False,
    )

    rc = cmd_get_connector(args, ctx=ctx, logger=ctx.logger)
    assert rc == 0


def test_get_connector_machine_outputs_smoke(capsys) -> None:
    """Команда `bkkt get-connector` не должна падать в json-режиме для found/not-found."""

    from connectctl.commands.get_connector_cmd import cmd_get_connector

    client = _FakeConnect()
    cluster = ConnectClusterConfig(
        env=Environment.dev, urls=list(client.base_urls), name="acme-external"
    )
    ctx = _DummyCtx(cluster=cluster, client=client, logger=_logger())

    found_args = argparse.Namespace(
        env="dev",
        cluster="acme-external",
        name="dev.payments.orders.source.postgres.cdc.0",
        status="short",
        meta=True,
        output="json",
        json=False,
        raw_status_json=False,
    )
    rc = cmd_get_connector(found_args, ctx=ctx, logger=ctx.logger)
    assert rc == 0
    found = capsys.readouterr().out
    assert '"found": true' in found

    missing_args = argparse.Namespace(
        env="dev",
        cluster="acme-external",
        name="dev.missing.connector.0",
        status="none",
        meta=False,
        output="json",
        json=False,
        raw_status_json=False,
    )
    rc = cmd_get_connector(missing_args, ctx=ctx, logger=ctx.logger)
    assert rc == 1
    missing = capsys.readouterr().out
    assert '"found": false' in missing


def test_connect_endpoints_json_smoke(capsys) -> None:
    from connectctl.commands.connect.endpoints_cmd import cmd_connect_endpoints

    client = _FakeConnect()
    cluster = ConnectClusterConfig(
        env=Environment.dev, urls=list(client.base_urls), name="acme-external"
    )
    ctx = _DummyCtx(cluster=cluster, client=client, logger=_logger())

    args = argparse.Namespace(
        env="dev",
        cluster="acme-external",
        name="dev.payments.orders.source.postgres.cdc.0",
        output="json",
        json=False,
    )

    rc = cmd_connect_endpoints(args, ctx=ctx, logger=ctx.logger)
    assert rc == 0
    out = capsys.readouterr().out
    assert '"endpoints"' in out
    assert '"healthy": true' in out


def test_connect_endpoints_text_uses_terminal_table(capsys) -> None:
    from connectctl.commands.connect.endpoints_cmd import cmd_connect_endpoints

    client = _FakeConnect()
    cluster = ConnectClusterConfig(
        env=Environment.dev, urls=list(client.base_urls), name="acme-external"
    )
    ctx = _DummyCtx(cluster=cluster, client=client, logger=_logger())

    args = argparse.Namespace(
        env="dev",
        cluster="acme-external",
        name="dev.payments.orders.source.postgres.cdc.0",
        output="text",
        json=False,
    )

    rc = cmd_connect_endpoints(args, ctx=ctx, logger=ctx.logger)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Endpoint" in out
    assert "http://dummy:8083" in out
    assert "┌" in out
    assert "│" in out
    assert "|---|" not in out


def test_connect_offsets_get_json_smoke(capsys) -> None:
    from connectctl.commands.connect.offsets_cmd import cmd_connect_offsets_get

    client = _FakeConnect()
    cluster = ConnectClusterConfig(
        env=Environment.dev, urls=list(client.base_urls), name="acme-external"
    )
    ctx = _DummyCtx(cluster=cluster, client=client, logger=_logger())

    args = argparse.Namespace(
        env="dev",
        cluster="acme-external",
        name="dev.payments.orders.source.postgres.cdc.0",
        output="json",
        json=False,
    )

    rc = cmd_connect_offsets_get(args, ctx=ctx, logger=ctx.logger)
    assert rc == 0
    out = capsys.readouterr().out
    assert '"offsets"' in out


def test_connect_offsets_patch_requires_yes(tmp_path) -> None:
    from connectctl.commands.connect.offsets_cmd import cmd_connect_offsets_patch
    from connectctl.exceptions import ConfigError

    client = _FakeConnect()
    cluster = ConnectClusterConfig(
        env=Environment.dev, urls=list(client.base_urls), name="acme-external"
    )
    ctx = _DummyCtx(cluster=cluster, client=client, logger=_logger())
    payload_path = tmp_path / "offsets.json"
    payload_path.write_text('{"offsets": []}\n')

    args = argparse.Namespace(
        env="dev",
        cluster="acme-external",
        name="dev.payments.orders.source.postgres.cdc.0",
        json_file=str(payload_path),
        dry_run=False,
        yes=False,
    )

    try:
        cmd_connect_offsets_patch(args, ctx=ctx, logger=ctx.logger)
    except ConfigError as e:
        assert "without --yes" in str(e)
    else:
        raise AssertionError("offsets patch without --yes must fail")


def test_connect_offsets_patch_dry_run(tmp_path) -> None:
    from connectctl.commands.connect.offsets_cmd import cmd_connect_offsets_patch

    client = _FakeConnect()
    cluster = ConnectClusterConfig(
        env=Environment.dev, urls=list(client.base_urls), name="acme-external"
    )
    ctx = _DummyCtx(cluster=cluster, client=client, logger=_logger())
    payload_path = tmp_path / "offsets.json"
    payload_path.write_text('{"offsets": []}\n')

    args = argparse.Namespace(
        env="dev",
        cluster="acme-external",
        name="dev.payments.orders.source.postgres.cdc.0",
        json_file=str(payload_path),
        dry_run=True,
        yes=False,
    )

    rc = cmd_connect_offsets_patch(args, ctx=ctx, logger=ctx.logger)
    assert rc == 0
