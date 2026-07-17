from __future__ import annotations


from connectctl.connect.client_validation import ConnectValidationMixin


def test_plugin_validation_errors_parsed_from_value_errors():
    result = {
        "name": "io.debezium.connector.postgresql.PostgresConnector",
        "error_count": 2,
        "configs": [
            {
                "definition": {"name": "database.hostname"},
                "value": {
                    "name": "database.hostname",
                    "errors": ['Missing required configuration "database.hostname".'],
                },
            },
            {
                "definition": {"name": "database.port"},
                "value": {
                    "name": "database.port",
                    "errors": [
                        'Invalid value "foo" for configuration "database.port".'
                    ],
                },
            },
        ],
    }

    out = ConnectValidationMixin._format_plugin_validation_errors(result)
    assert "- database.hostname:" in out
    assert "Missing required configuration" in out
    assert "- database.port:" in out


def test_common_validation_hints_change_me_and_unresolved_placeholder():
    cfg = {
        "database.hostname": "CHANGE_ME_DB_HOST",
        "database.port": "CHANGE_ME_DB_PORT",
        "snapshot.mode": "${debezium_snapshot_mode_init:-initial}",
        "database.password": "${secretManager:dbz-acme-prod:password}",
    }

    hints = ConnectValidationMixin._detect_common_validation_hints(cfg)
    assert "CHANGE_ME" in hints
    assert "snapshot.mode" in hints
    # Do not warn on Kafka Connect ConfigProvider placeholders.
    assert "secretManager" not in hints


def test_common_validation_hints_do_not_flag_port_if_config_provider_placeholder():
    cfg = {
        "database.port": "${secretManager:dbz-acme-prod:port}",
        "database.hostname": "${secretManager:dbz-acme-prod:hostname}",
    }

    hints = ConnectValidationMixin._detect_common_validation_hints(cfg)
    # Secret placeholders must not trigger generic port warnings.
    assert "database.port" not in hints
