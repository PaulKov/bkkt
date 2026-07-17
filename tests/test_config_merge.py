import json
from pathlib import Path

from connectctl.models import RepoConfig
from connectctl.repo import ConnectorRepo, LayerResolver
from connectctl.rendering import ConnectorRenderer


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def test_layered_overrides_precedence(tmp_path: Path):
    # Arrange repo structure
    repo_root = tmp_path

    _write_json(
        repo_root / "__global/all.json",
        {"transforms": "convertTimezone,replaceTopicName"},
    )
    _write_json(repo_root / "acme/source/all.json", {"transforms": "convertTimezone"})

    # base file in your repo style: flat config fragment + optional name
    base = {
        "name": "${global.connector.name}",
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        "snapshot.mode": "initial",
    }

    # env-specific manifest (wrapper)
    env_manifest = {
        "name": "prod.acme.configuration.source.postgres.0",
        "config": {"topic.prefix": "prod.acme.configuration.source.postgres.0"},
    }

    connector_dir = repo_root / "acme/source/postgres/connector_acme__configuration"
    _write_json(
        connector_dir / "base.source_acme__configuration__common_tables.json", base
    )
    _write_json(
        connector_dir / "prod_source_acme__configuration__common_tables.json",
        env_manifest,
    )

    cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    repo = ConnectorRepo(cfg)
    renderer = ConnectorRenderer(repo=repo, layers=LayerResolver(cfg))

    # Act
    rr = renderer.render(
        connector_dir / "prod_source_acme__configuration__common_tables.json"
    )

    # Assert: transforms from acme/source/all.json overrides __global/all.json
    assert rr.manifest.config["transforms"] == "convertTimezone"
    assert rr.manifest.name == "prod.acme.configuration.source.postgres.0"
    assert (
        rr.manifest.config["connector.class"]
        == "io.debezium.connector.postgresql.PostgresConnector"
    )
