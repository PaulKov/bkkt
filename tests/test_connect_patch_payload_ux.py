from __future__ import annotations

import argparse

import pytest

from connectctl.cli_helpers import patch_io_kv
from connectctl.cli_helpers.patch_io_kv import _parse_kv_pairs, _parse_kv_text
from connectctl.cli_helpers.patch_io_payload import _read_patch_payload
from connectctl.exceptions import ConfigError


def test_parse_set_literal_preserves_commas_in_value() -> None:
    parse_literal = getattr(patch_io_kv, "_parse_kv_literal", None)

    assert parse_literal is not None
    assert parse_literal("table.include.list=orders.a,orders.b,orders.c") == {
        "table.include.list": "orders.a,orders.b,orders.c"
    }


def test_parse_set_csv_keeps_legacy_comma_separated_pairs() -> None:
    assert _parse_kv_pairs("a=b,c=d") == {"a": "b", "c": "d"}


def test_parse_set_file_text_uses_one_literal_pair_per_line() -> None:
    assert (
        _parse_kv_text(
            """
        # comments are ignored
        table.include.list=orders.a,orders.b,orders.c
        errors.max.retries=1440
        """
        )
        == {
            "table.include.list": "orders.a,orders.b,orders.c",
            "errors.max.retries": "1440",
        }
    )


def test_parse_set_literal_error_points_to_copy_paste_safe_examples() -> None:
    parse_literal = getattr(patch_io_kv, "_parse_kv_literal", None)

    assert parse_literal is not None
    with pytest.raises(ConfigError) as exc:
        parse_literal("orders.mirror_check_results")

    message = str(exc.value)
    assert "--set 'table.include.list=a,b,c'" in message
    assert "--json-file" in message


def test_read_patch_payload_combines_literal_set_and_legacy_set_csv() -> None:
    args = argparse.Namespace(
        json_file=[],
        json=[],
        set_file=[],
        set=["table.include.list=orders.a,orders.b"],
        set_csv=["errors.max.retries=1440,errors.retry.delay.max.ms=60000"],
        stdin=False,
    )

    assert _read_patch_payload(args) == {
        "table.include.list": "orders.a,orders.b",
        "errors.max.retries": "1440",
        "errors.retry.delay.max.ms": "60000",
    }
