from __future__ import annotations


from connectctl.utils.placeholders import resolve_placeholders


def test_default_placeholder_resolves_from_context():
    ctx = {"debezium_snapshot_mode_init": "initial_only"}
    assert (
        resolve_placeholders("${debezium_snapshot_mode_init:-initial}", ctx)
        == "initial_only"
    )


def test_default_placeholder_uses_default_when_missing():
    assert (
        resolve_placeholders("${debezium_snapshot_mode_init:-initial}", {}) == "initial"
    )


def test_config_provider_placeholders_are_preserved():
    # Kafka Connect ConfigProvider placeholders must stay intact.
    assert (
        resolve_placeholders("${secretManager:prod/x:y}", {})
        == "${secretManager:prod/x:y}"
    )


def test_nested_var_inside_config_provider_is_resolved():
    # Inner BKKT placeholder should be resolved, while the outer provider placeholder stays.
    ctx = {"db.secret": "dbz-acme-prod"}
    assert (
        resolve_placeholders("${secretManager:${db.secret}:password}", ctx)
        == "${secretManager:dbz-acme-prod:password}"
    )
