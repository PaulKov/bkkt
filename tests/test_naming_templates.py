import json
from pathlib import Path

import pytest

from connectctl.exceptions import ValidationError
from connectctl.repo import ConnectorRepo, LayerResolver
from connectctl.rendering import ConnectorRenderer
from connectctl.settings import Settings
from connectctl.validation import validate_strict_naming


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def test_naming_template_rules_source_and_sink(tmp_path: Path):
    """Strict naming rules are configurable via connectctl.yaml (templates).

    This test covers both a Debezium-style source connector and an Iceberg sink.
    """

    repo_root = tmp_path
    cfg_path = repo_root / "connectctl.yaml"
    cfg_path.write_text(
        """
clusters:
  stage:
    connect:
      hosts: ["127.0.0.1"]
  dev:
    connect:
      hosts: ["127.0.0.1"]
  prod:
    connect:
      hosts: ["127.0.0.1"]

naming:
  enabled: true
  strict: true
  rules:
    - id: source_default
      applies_to: { type: ["source"] }
      template: "{env}.{domain}.{dataset}.source.{system}.{index}"
    - id: sink_default
      applies_to: { type: ["sink"] }
      template: "{env}.{domain}.{dataset}.sink.{layer}.{system}.{index}"
""",
        encoding="utf-8",
    )

    # Minimal source connector (dataset inferred from database.dbname)
    src_path = (
        repo_root
        / "acme/source/postgres/connector_acme__configuration/stage_source_acme__configuration__common_tables.json"
    )
    _write_json(
        src_path,
        {
            "name": "stage.acme.configuration.source.postgres.0",
            "config": {
                "name": "stage.acme.configuration.source.postgres.0",
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.dbname": "configuration",
            },
        },
    )

    # Minimal sink connector (layer inferred from filename, dataset from slug => acme_configuration)
    sink_path = (
        repo_root
        / "acme/sink/iceberg/connector_acme__configuration/stage_sink_ods_acme__configuration__common_tables.json"
    )
    _write_json(
        sink_path,
        {
            "name": "stage.acme.acme_configuration.sink.ods.iceberg.0",
            "config": {
                "name": "stage.acme.acme_configuration.sink.ods.iceberg.0",
                "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
                "topics": "cdc.stage.acme.acme_configuration.public.providers.0",
            },
        },
    )

    settings = Settings.load(cfg_path, repo_root=repo_root)
    repo = ConnectorRepo(settings.repo)
    renderer = ConnectorRenderer(repo=repo, layers=LayerResolver(settings.repo))

    for p in [src_path, sink_path]:
        rr = renderer.render(p)
        validate_strict_naming(rr.manifest, naming=settings.naming)


def test_naming_template_detects_wrong_dataset(tmp_path: Path):
    repo_root = tmp_path
    cfg_path = repo_root / "connectctl.yaml"
    cfg_path.write_text(
        """
clusters:
  stage:
    connect:
      hosts: ["127.0.0.1"]

naming:
  enabled: true
  strict: true
  rules:
    - id: source_default
      applies_to: { type: ["source"] }
      template: "{env}.{domain}.{dataset}.source.{system}.{index}"
""",
        encoding="utf-8",
    )

    p = (
        repo_root
        / "acme/source/postgres/connector_acme__configuration/stage_source_acme__configuration__common_tables.json"
    )
    _write_json(
        p,
        {
            # dataset should be 'configuration', but name contains 'wrong'
            "name": "stage.acme.wrong.source.postgres.0",
            "config": {
                "name": "stage.acme.wrong.source.postgres.0",
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.dbname": "configuration",
            },
        },
    )

    settings = Settings.load(cfg_path, repo_root=repo_root)
    repo = ConnectorRepo(settings.repo)
    renderer = ConnectorRenderer(repo=repo, layers=LayerResolver(settings.repo))
    rr = renderer.render(p)

    with pytest.raises(ValidationError):
        validate_strict_naming(rr.manifest, naming=settings.naming)


def test_naming_template_source_dataset_does_not_break_on_secretmanager_placeholder(
    tmp_path: Path,
):
    """Regression test.

    For Debezium-like sources `database.dbname` is often stored via Kafka Connect
    config providers, e.g. `${secretManager:prod/...:dbname}`.

    Strict naming must NOT treat the placeholder string as a literal dataset name,
    otherwise it would generate an impossible expected regex.
    """

    repo_root = tmp_path
    cfg_path = repo_root / "connectctl.yaml"
    cfg_path.write_text(
        """
clusters:
  prod:
    connect:
      hosts: ["127.0.0.1"]

naming:
  enabled: true
  strict: true
  rules:
    - id: source_default
      applies_to: { type: ["source"] }
      template: "{env}.{domain}.{dataset}.source.{system}.{index}"
""",
        encoding="utf-8",
    )

    p = (
        repo_root
        / "gamemode/source/postgres/connector_gamemode/prod.gamemode.gamemode.source.postgres.cdc.2.json"
    )
    _write_json(
        p,
        {
            "name": "prod.gamemode.gamemode.source.postgres.cdc.2",
            "config": {
                "name": "prod.gamemode.gamemode.source.postgres.cdc.2",
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.dbname": "${secretManager:prod/gamemode/gamemode:dbname}",
            },
        },
    )

    settings = Settings.load(cfg_path, repo_root=repo_root)
    repo = ConnectorRepo(settings.repo)
    renderer = ConnectorRenderer(repo=repo, layers=LayerResolver(settings.repo))

    rr = renderer.render(p)
    validate_strict_naming(rr.manifest, naming=settings.naming)
