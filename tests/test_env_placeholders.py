from __future__ import annotations

from connectctl.utils.placeholders import resolve_placeholders


def test_env_default_used_when_missing(monkeypatch):
    monkeypatch.delenv("AWS_REGION", raising=False)
    out = resolve_placeholders("${AWS_REGION:-eu-central-1}", {})
    assert out == "eu-central-1"


def test_env_value_overrides_default(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    out = resolve_placeholders("${AWS_REGION:-eu-central-1}", {})
    assert out == "us-east-1"


def test_env_placeholder_no_default(monkeypatch):
    monkeypatch.setenv("FOO", "bar")
    out = resolve_placeholders("${FOO}", {})
    assert out == "bar"


def test_config_provider_placeholder_is_preserved():
    out = resolve_placeholders("${secretManager:some/key}", {"some": "x"})
    assert out == "${secretManager:some/key}"


def test_nested_placeholder_inside_config_provider_is_resolved():
    out = resolve_placeholders("${secretManager:${x}:password}", {"x": "dbz-acme-prod"})
    assert out == "${secretManager:dbz-acme-prod:password}"
