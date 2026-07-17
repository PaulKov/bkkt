from __future__ import annotations

from types import SimpleNamespace

from connectctl.cli_helpers.timeout_args import timeout_seconds_from_args


def test_timeout_seconds_from_args_uses_default_for_missing_or_none() -> None:
    assert timeout_seconds_from_args(SimpleNamespace(), default=300.0) == 300.0
    assert (
        timeout_seconds_from_args(SimpleNamespace(timeout_seconds=None), default=300.0)
        == 300.0
    )


def test_timeout_seconds_from_args_preserves_explicit_value() -> None:
    assert (
        timeout_seconds_from_args(SimpleNamespace(timeout_seconds="42"), default=300.0)
        == 42.0
    )
