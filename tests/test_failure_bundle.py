from __future__ import annotations

import json
from pathlib import Path

from connectctl.adapters.filesystem import LocalFileSystem
from connectctl.exceptions import ConfigError, ConnectApiError
from connectctl.services.failure_bundle import FailureBundleWriter


def test_failure_bundle_adds_tls_specific_remediation(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    writer = FailureBundleWriter(
        command="apply",
        repo_root=tmp_path,
        fs=fs,
        root_dir=tmp_path / "failure-bundles" / "apply",
    )

    bundle_dir = writer.write(
        env="prod",
        stage="deploy",
        error=ConnectApiError(
            "org.apache.kafka.common.errors.SslAuthenticationException: SSL handshake failed; "
            "PKIX path building failed: unable to find valid certification path"
        ),
        manifest_meta={
            "path": "payments/sink/iceberg/connector_payments__orders/prod.payments.orders.sink.raw.iceberg.0.json",
            "name": "prod.payments.orders.sink.raw.iceberg.0",
            "cluster_group": "acme-external",
        },
        routing_payload={
            "cluster": {
                "group": "acme-external",
                "env": "prod",
                "urls": ["http://external:8083"],
            },
            "source": "tag",
            "target": "acme-external/prod",
        },
        pruned_config_keys=["bootstrap.servers"],
    )

    bundle = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
    readme = (bundle_dir / "README.md").read_text(encoding="utf-8")

    assert bundle["remediation"]["category"] == "tls_truststore"
    assert (
        "does not trust the broker certificate chain"
        in bundle["remediation"]["summary"]
    )
    assert any(
        cmd.startswith(
            "bkkt get-connector --env prod --cluster acme-external --status long"
        )
        for cmd in bundle["remediation"]["commands"]
    )
    assert any(
        cmd.startswith(
            "bkkt connect restart --env prod --cluster acme-external --names prod.payments.orders.sink.raw.iceberg.0 --scope failed-tasks --dry-run"
        )
        for cmd in bundle["remediation"]["commands"]
    )
    assert any(
        cmd.startswith(
            "bkkt connect restart --env prod --clusters acme-external --scope failed-tasks --dry-run"
        )
        for cmd in bundle["remediation"]["commands"]
    )
    assert "docs/CONNECTCTL_RUNBOOK.md" in readme


def test_failure_bundle_adds_connect_create_exists_remediation(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    writer = FailureBundleWriter(
        command="connect-create",
        repo_root=tmp_path,
        fs=fs,
        root_dir=tmp_path / "failure-bundles" / "connect-create",
    )

    bundle_dir = writer.write(
        env="dev",
        stage="create",
        error=ConfigError(
            "Коннектор уже существует: dev.demo.orders.source.postgres.cdc.0 (используйте update)"
        ),
        manifest_meta={
            "name": "dev.demo.orders.source.postgres.cdc.0",
            "cluster_group": "acme-external",
        },
        extra={
            "name": "dev.demo.orders.source.postgres.cdc.0",
            "cluster_group": "acme-external",
            "input_src": "./connector.json",
        },
    )

    bundle = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
    readme = (bundle_dir / "README.md").read_text(encoding="utf-8")

    assert bundle["remediation"]["category"] == "connector_exists"
    assert (
        "already exists on the selected Kafka Connect cluster"
        in bundle["remediation"]["summary"]
    )
    assert any(
        cmd.startswith(
            "bkkt get-connector --env dev --cluster acme-external --status long dev.demo.orders.source.postgres.cdc.0"
        )
        for cmd in bundle["remediation"]["commands"]
    )
    assert any(
        cmd.startswith(
            "bkkt connect update --env dev --cluster acme-external --name dev.demo.orders.source.postgres.cdc.0 ./connector.json --dry-run --diff"
        )
        for cmd in bundle["remediation"]["commands"]
    )
    assert "connect patch --dry-run --diff" in readme


def test_failure_bundle_adds_connect_patch_missing_remediation(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    writer = FailureBundleWriter(
        command="connect-patch",
        repo_root=tmp_path,
        fs=fs,
        root_dir=tmp_path / "failure-bundles" / "connect-patch",
    )

    bundle_dir = writer.write(
        env="prod",
        stage="fetch_config",
        error=ConfigError(
            "Коннектор не существует: prod.demo.orders.sink.raw.iceberg.0 (используйте create)"
        ),
        manifest_meta={
            "name": "prod.demo.orders.sink.raw.iceberg.0",
            "cluster_group": "acme-external",
        },
        extra={
            "name": "prod.demo.orders.sink.raw.iceberg.0",
            "cluster_group": "acme-external",
        },
    )

    bundle = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
    readme = (bundle_dir / "README.md").read_text(encoding="utf-8")

    assert bundle["remediation"]["category"] == "connector_missing"
    assert (
        "was not found on the selected Kafka Connect cluster"
        in bundle["remediation"]["summary"]
    )
    assert any(
        cmd.startswith(
            "bkkt connect status --env prod --cluster acme-external --status short"
        )
        for cmd in bundle["remediation"]["commands"]
    )
    assert any(
        cmd.startswith(
            "bkkt get-connector --env prod --cluster acme-external --status long prod.demo.orders.sink.raw.iceberg.0"
        )
        for cmd in bundle["remediation"]["commands"]
    )
    assert "switch to `connect create`" in readme


def test_failure_bundle_compare_command_does_not_include_env_flag(
    tmp_path: Path,
) -> None:
    fs = LocalFileSystem()
    writer = FailureBundleWriter(
        command="apply",
        repo_root=tmp_path,
        fs=fs,
        root_dir=tmp_path / "failure-bundles" / "apply",
    )

    bundle_dir = writer.write(
        env="prod",
        stage="deploy",
        error=ConnectApiError("Kafka Connect rejected the update"),
        manifest_meta={
            "path": "vegas/sink/iceberg/connector_vegas__aggregator/prod.vegas.aggregator.sink.raw.iceberg.1.json",
            "name": "prod.vegas.aggregator.sink.raw.iceberg.1",
            "cluster_group": "acme-external_foreign_kafka_dev_legacy",
        },
        routing_payload={
            "cluster": {
                "group": "acme-external_foreign_kafka_dev_legacy",
                "env": "prod",
                "urls": ["http://external-dev:8083"],
            },
            "source": "tag",
            "target": "acme-external_foreign_kafka_dev_legacy/prod",
        },
    )

    bundle = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
    commands = bundle["remediation"]["commands"]

    assert any(
        cmd.startswith(
            "bkkt compare vegas/sink/iceberg/connector_vegas__aggregator/prod.vegas.aggregator.sink.raw.iceberg.1.json --cluster acme-external_foreign_kafka_dev_legacy"
        )
        for cmd in commands
    )
    assert not any(cmd.startswith("bkkt compare --env ") for cmd in commands)


def test_failure_bundle_adds_endpoint_health_remediation(tmp_path: Path) -> None:
    fs = LocalFileSystem()
    writer = FailureBundleWriter(
        command="apply",
        repo_root=tmp_path,
        fs=fs,
        root_dir=tmp_path / "failure-bundles" / "apply",
    )

    bundle_dir = writer.write(
        env="prod",
        stage="deploy",
        error=ConnectApiError(
            "Kafka Connect request failed on all endpoints: GET /connectors/demo/config"
        ),
        manifest_meta={
            "name": "prod.demo.orders.sink.raw.iceberg.0",
            "cluster_group": "acme-external",
        },
    )

    bundle = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
    commands = bundle["remediation"]["commands"]

    assert bundle["remediation"]["category"] == "connect_endpoint_health"
    assert any(
        cmd.startswith(
            "bkkt connect endpoints --env prod --cluster acme-external --name prod.demo.orders.sink.raw.iceberg.0"
        )
        for cmd in commands
    )
