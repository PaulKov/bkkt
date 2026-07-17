from __future__ import annotations

from pathlib import Path

from connectctl.models import (
    ConnectorManifest,
    ConnectorPathInfo,
    ConnectorType,
    Environment,
)
from connectctl.validation.policies_static import lint_static_layers


def test_lint_static_layers_ignores_pruned_keys() -> None:
    manifest = ConnectorManifest(
        name="prod.vegas.aggregator.sink.raw.iceberg.1",
        config={},
        source_path=Path("/tmp/prod.vegas.aggregator.sink.raw.iceberg.1.json"),
        info=ConnectorPathInfo(
            path=Path("/tmp/prod.vegas.aggregator.sink.raw.iceberg.1.json"),
            relpath=Path("x/prod.vegas.aggregator.sink.raw.iceberg.1.json"),
            domain="vegas",
            connector_type=ConnectorType.sink,
            system="iceberg",
            connector_dir="connector_vegas__aggregator",
            env=Environment.prod,
            remainder="",
            mode=None,
        ),
    )

    layer = Path("/tmp/prod.vegas.aggregator.sink.raw.iceberg.1.json")
    layer.write_text(
        """{
  "config": {
    "iceberg.kafka.bootstrap.servers": "b-1.example:9096,b-2.example:9096"
  }
}
"""
    )

    issues = lint_static_layers(
        manifest,
        env=Environment.prod,
        layers=[layer],
        ignored_keys=("iceberg.kafka.*",),
    )

    assert issues == []
