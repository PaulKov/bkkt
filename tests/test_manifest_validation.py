from __future__ import annotations

from pathlib import Path

import pytest

from connectctl.cli import _validate_manifest
from connectctl.exceptions import ValidationError
from connectctl.models import (
    ConnectorManifest,
    ConnectorPathInfo,
    ConnectorType,
    Environment,
)


def _mk_manifest(
    config: dict, *, name: str = "stage.dom.ds.source.sys.0"
) -> ConnectorManifest:
    info = ConnectorPathInfo(
        path=Path("/tmp/x.json"),
        relpath=Path("x.json"),
        domain="dom",
        connector_type=ConnectorType.source,
        system="sys",
        connector_dir="connector_dom__ds",
        env=Environment.stage,
        remainder="source_dom__ds",
        mode=None,
    )
    return ConnectorManifest(
        name=name, config=config, source_path=Path("/tmp/x.json"), info=info
    )


def test_validate_manifest_rejects_non_string_values():
    m = _mk_manifest({"connector.class": "X", "tasks.max": 1})  # int value is invalid
    with pytest.raises(ValidationError):
        _validate_manifest(m)


def test_validate_manifest_rejects_mismatching_name_in_config():
    m = _mk_manifest({"connector.class": "X", "tasks.max": "1", "name": "other"})
    with pytest.raises(ValidationError):
        _validate_manifest(m)


def test_validate_manifest_rejects_unresolved_placeholders_without_provider():
    m = _mk_manifest({"connector.class": "X", "tasks.max": "1", "foo": "${missing}"})
    with pytest.raises(ValidationError):
        _validate_manifest(m)


def test_validate_manifest_allows_config_provider_placeholders():
    m = _mk_manifest(
        {
            "connector.class": "X",
            "tasks.max": "1",
            "database.user": "${secretManager:db:username}",
        }
    )
    _validate_manifest(m)


def test_validate_manifest_rejects_unresolved_function_placeholders():
    m = _mk_manifest(
        {
            "connector.class": "X",
            "tasks.max": "1",
            "database.server.id": "${fn:hash_int(connector.name)}",
        }
    )
    with pytest.raises(ValidationError):
        _validate_manifest(m)
