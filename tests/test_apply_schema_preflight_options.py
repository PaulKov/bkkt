from __future__ import annotations

import argparse

import pytest

from connectctl.exceptions import ConfigError
from connectctl.models import Environment
from connectctl.services.apply.deploy_options import ApplyOptions


def _args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "dry_run": False,
        "schema_preflight": True,
        "schema_preflight_reason": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_apply_options_require_reason_for_schema_preflight_break_glass() -> None:
    with pytest.raises(ConfigError, match="schema-preflight-reason"):
        ApplyOptions.from_args(
            _args(schema_preflight=False),
            env=Environment.prod,
        )


def test_apply_options_accept_schema_preflight_break_glass_with_reason() -> None:
    options = ApplyOptions.from_args(
        _args(
            schema_preflight=False,
            schema_preflight_reason="Emergency rollback after SR owner approval",
        ),
        env=Environment.prod,
    )

    assert options.schema_preflight is False
    assert (
        options.schema_preflight_reason == "Emergency rollback after SR owner approval"
    )
