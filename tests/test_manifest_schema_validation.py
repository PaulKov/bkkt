from __future__ import annotations

from pathlib import Path

from connectctl.adapters.filesystem_local import LocalFileSystem
from connectctl.validation.schema_validation import load_schema, validate_instance


def test_manifest_schema_allows_export_comments() -> None:
    fs = LocalFileSystem()
    schema = load_schema(
        Path("connectctl/assets/repo_defaults/schemas/manifest.schema.json"),
        fs=fs,
    )
    instance = {
        "name": "prod.demo.demo.sink.raw.iceberg.0",
        "config": {
            "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
            "name": "prod.demo.demo.sink.raw.iceberg.0",
        },
        "__export_comments__": {
            "name": "override candidate: __global/sink/iceberg/all.json -> prod.demo.demo.sink.raw.iceberg.0",
        },
    }

    issues = validate_instance(
        instance,
        schema=schema,
        file=Path("/tmp/manifest.json"),
    )

    assert issues == []


def test_manifest_schema_allows_connectctl_lifecycle() -> None:
    fs = LocalFileSystem()
    schema = load_schema(
        Path("connectctl/assets/repo_defaults/schemas/manifest.schema.json"),
        fs=fs,
    )
    instance = {
        "name": "prod.demo.demo.sink.raw.iceberg.0",
        "connectctl": {
            "lifecycle": {
                "disabled": True,
                "reason": "Source retired",
                "ticket": "OPS-123",
                "until": "2026-05-01",
            }
        },
        "config": {
            "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
            "name": "prod.demo.demo.sink.raw.iceberg.0",
        },
    }

    issues = validate_instance(
        instance,
        schema=schema,
        file=Path("/tmp/manifest.json"),
    )

    assert issues == []


def test_manifest_schema_allows_bkkt_unset_config_keys() -> None:
    fs = LocalFileSystem()
    schema = load_schema(
        Path("connectctl/assets/repo_defaults/schemas/manifest.schema.json"),
        fs=fs,
    )
    instance = {
        "name": "prod.demo.demo.sink.raw.iceberg.0",
        "bkkt": {
            "unset_config_keys": [
                "iceberg.tables.write-props.write.target-file-size-bytes",
            ],
        },
        "config": {
            "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
        },
    }

    issues = validate_instance(
        instance,
        schema=schema,
        file=Path("/tmp/manifest.json"),
    )

    assert issues == []


def test_connectctl_schema_allows_cluster_lifecycle() -> None:
    fs = LocalFileSystem()
    schema = load_schema(
        Path("connectctl/assets/repo_defaults/schemas/connectctl.schema.json"),
        fs=fs,
    )
    instance = {
        "default_cluster": "acme-main",
        "cluster_lifecycle": {
            "overrides": [
                {
                    "cluster": "acme-source",
                    "env": "dev",
                    "disabled": True,
                    "reason": "alias disabled by platform owner",
                    "ticket": "DATAPLAT-2652",
                }
            ]
        },
        "clusters": {
            "acme-main": {
                "lifecycle": {
                    "disabled": True,
                    "reason": "dev worker intentionally stopped",
                    "ticket": "DATAPLAT-2652",
                },
                "dev": {
                    "connect": {
                        "scheme": "http",
                        "port": 8083,
                        "hosts": ["connect-dev-main"],
                    }
                },
            },
            "acme-source": {
                "dev": "from_cluster_group_env(acme-main, 'all')",
            },
        },
    }

    issues = validate_instance(
        instance,
        schema=schema,
        file=Path("/tmp/connectctl.yaml"),
    )

    assert issues == []
