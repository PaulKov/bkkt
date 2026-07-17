from __future__ import annotations

import pytest

from connectctl.utils.placeholders import resolve_placeholders


def test_fn_hash_int_is_deterministic_and_in_range():
    ctx = {
        "connector.name": "prod.merchants.acme_common.source.mariadb.cdc.dbt.0",
    }
    out1 = resolve_placeholders("${fn:hash_int(connector.name, mod=4294967295)}", ctx)
    out2 = resolve_placeholders("${fn:hash_int(connector.name, mod=4294967295)}", ctx)
    assert out1 == out2
    assert out1.isdigit()
    n = int(out1)
    assert 1 <= n <= 4294967294


def test_fn_hash_int_supports_salt():
    ctx = {"connector.name": "x"}
    a = resolve_placeholders("${fn:hash_int(connector.name, salt='a')}", ctx)
    b = resolve_placeholders("${fn:hash_int(connector.name, salt='b')}", ctx)
    assert a != b


def test_fn_hash_int_uses_structured_salt_mix():
    ctx1 = {"connector.name": "c"}
    ctx2 = {"connector.name": "bc"}
    a = resolve_placeholders("${fn:hash_int(connector.name, salt='ab')}", ctx1)
    b = resolve_placeholders("${fn:hash_int(connector.name, salt='a')}", ctx2)
    assert a != b


def test_unknown_function_raises():
    ctx = {"connector.name": "x"}
    with pytest.raises(ValueError):
        resolve_placeholders("${fn:nope(connector.name)}", ctx)
