from __future__ import annotations


from pathlib import Path

import pytest

from connectctl.connect.client_validation import ConnectValidationMixin
from connectctl.exceptions import ValidationError
from connectctl.models import (
    ConnectorManifest,
    ConnectorPathInfo,
    ConnectorType,
    Environment,
)


class _FakeLogger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, msg: str, *args, **kwargs) -> None:  # pragma: no cover
        # Mimic stdlib logging formatting.
        try:
            self.warnings.append(msg % args)
        except Exception:
            self.warnings.append(msg)


class _FakeConnect(ConnectValidationMixin):
    """A tiny fake Connect client.

    We emulate two behaviours:
    - raw validate fails on ConfigProvider placeholders
    - validate passes on sanitized values
    - missing required fields still fail
    """

    def __init__(self) -> None:
        self._log = _FakeLogger()
        self.calls: list[dict] = []

    def validate_config(self, connector_class: str, config: dict) -> dict:
        self.calls.append(dict(config))

        # If hostname is still a ConfigProvider placeholder, pretend Connect validates raw strings.
        if str(config.get("database.hostname", "")).startswith("${secretManager:"):
            return {
                "name": connector_class,
                "error_count": 1,
                "configs": [
                    {
                        "definition": {"name": "database.hostname"},
                        "value": {
                            "name": "database.hostname",
                            "errors": ["invalid format"],
                        },
                    }
                ],
            }

        # Simulate a real required field.
        if not str(config.get("database.dbname") or "").strip():
            return {
                "name": connector_class,
                "error_count": 1,
                "configs": [
                    {
                        "definition": {"name": "database.dbname"},
                        "value": {
                            "name": "database.dbname",
                            "errors": ["A value is required"],
                        },
                    }
                ],
            }

        return {"name": connector_class, "error_count": 0, "configs": []}


def _manifest(config: dict) -> ConnectorManifest:
    info = ConnectorPathInfo(
        path=Path(
            "/repo/acme/source/postgres/connector_acme__operations/prod.acme.operations.source.postgres.init.0.json"
        ),
        relpath=Path(
            "acme/source/postgres/connector_acme__operations/prod.acme.operations.source.postgres.init.0.json"
        ),
        domain="acme",
        connector_type=ConnectorType.source,
        system="postgres",
        connector_dir="connector_acme__operations",
        env=Environment.prod,
        remainder="prod.acme.operations.source.postgres.init.0",
        variant=None,
        mode="init",
    )
    return ConnectorManifest(
        name=str(config.get("name") or "prod.acme.operations.source.postgres.init.0"),
        config=config,
        source_path=info.path,
        info=info,
    )


def test_validate_manifest_succeeds_after_placeholder_substitution():
    connect = _FakeConnect()
    cfg = {
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        "name": "prod.acme.operations.source.postgres.init.0",
        "database.hostname": "${secretManager:dbz-acme-prod:hostname}",
        "database.port": "${secretManager:dbz-acme-prod:port}",
        "database.dbname": "acme",
    }

    res = connect.validate_manifest(_manifest(cfg))
    assert res.get("_bkkt", {}).get("validation_mode") == "placeholder-substitution"
    assert "database.hostname" in res.get("_bkkt", {}).get("replaced_fields", [])
    assert (
        connect._log.warnings
    ), "Should warn that validate endpoint may not resolve ConfigProviders"
    # Two-pass validate (raw + sanitized)
    assert len(connect.calls) == 2


def test_validate_manifest_fails_if_real_errors_remain_after_substitution():
    connect = _FakeConnect()
    cfg = {
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        "name": "prod.acme.operations.source.postgres.init.0",
        "database.hostname": "${secretManager:dbz-acme-prod:hostname}",
        "database.port": "${secretManager:dbz-acme-prod:port}",
        # Missing dbname should still fail.
        "database.dbname": "",
    }

    with pytest.raises(ValidationError) as e:
        connect.validate_manifest(_manifest(cfg))

    msg = str(e.value)
    assert "database.dbname" in msg
    assert "After placeholder substitution" in msg
    assert "Replaced fields" in msg
