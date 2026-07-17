import json
from dataclasses import replace
from pathlib import Path

from connectctl.config_models import NamingConfig, NamingRule
from connectctl.models import RepoConfig
from connectctl.rendering import ConnectorRenderer
from connectctl.repo import ConnectorRepo, LayerResolver
from connectctl.validation import build_naming_lint_markdown, lint_strict_naming


def _renderer(repo_root: Path) -> ConnectorRenderer:
    cfg = RepoConfig(root=repo_root, connectors_root=repo_root, ignore_dirs=())
    repo = ConnectorRepo(cfg)
    layers = LayerResolver(cfg)
    return ConnectorRenderer(repo=repo, layers=layers)


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _naming_cfg() -> NamingConfig:
    # Эти правила эквивалентны дефолтным правилам из connectctl.yaml в основном репозитории.
    return NamingConfig(
        enabled=True,
        strict=True,
        rules=(
            NamingRule(
                id="source_default",
                applies_to={"type": ("source",)},
                template="{env}.{domain}.{dataset}.source.{system}.{index}",
                description="<env>.<domain>.<dataset>.source.<system>.<index>",
            ),
            NamingRule(
                id="sink_default",
                applies_to={"type": ("sink",)},
                template="{env}.{domain}.{dataset}.sink.{layer}.{system}.{index}",
                description="<env>.<domain>.<dataset>.sink.<layer>.<system>.<index>",
            ),
        ),
    )


def test_naming_lint_suggests_expected_name_for_source(tmp_path: Path) -> None:
    repo_root = tmp_path
    naming = _naming_cfg()

    p = (
        repo_root
        / "acme/source/postgres/connector_acme__configuration/stage_source_acme__configuration.json"
    )
    _write_json(
        p,
        {
            "name": "stage.acme.configuration.source.postgres.0",
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "tasks.max": "1",
                "database.dbname": "configuration",
            },
        },
    )

    r = _renderer(repo_root)
    rr = r.render(p)

    # Make the name wrong (dataset segment), but keep config.name consistent.
    wrong_name = "stage.acme.WRONG.source.postgres.0"
    cfg = dict(rr.manifest.config)
    cfg["name"] = wrong_name
    bad = replace(rr.manifest, name=wrong_name, config=cfg)

    issue = lint_strict_naming(bad, naming=naming)
    assert issue is not None
    # Expected dataset is inferred from config["database.dbname"] == "configuration"
    assert issue.suggested_name == "stage.acme.configuration.source.postgres.0"
    assert issue.expected_template == "{env}.{domain}.{dataset}.source.{system}.{index}"

    md = build_naming_lint_markdown([issue])
    assert "stage.acme.configuration.source.postgres.0" in md
    assert "stage.acme.WRONG.source.postgres.0" in md


def test_naming_lint_suggests_expected_name_for_sink(tmp_path: Path) -> None:
    repo_root = tmp_path
    naming = _naming_cfg()

    p = (
        repo_root
        / "acme/sink/iceberg/connector_acme__acme_configuration/stage.acme.acme_configuration.sink.ods.iceberg.0.json"
    )
    _write_json(
        p,
        {
            "name": "stage.acme.acme_configuration.sink.ods.iceberg.0",
            "config": {
                "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
                "tasks.max": "1",
                "topics": "acme_configuration",
            },
        },
    )

    r = _renderer(repo_root)
    rr = r.render(p)

    # Wrong sink layer in the name (should be ods by filename convention).
    wrong_name = "stage.acme.acme_configuration.sink.raw.iceberg.0"
    cfg = dict(rr.manifest.config)
    cfg["name"] = wrong_name
    bad = replace(rr.manifest, name=wrong_name, config=cfg)

    issue = lint_strict_naming(bad, naming=naming)
    assert issue is not None
    assert issue.suggested_name == "stage.acme.acme_configuration.sink.ods.iceberg.0"
    assert (
        issue.expected_template
        == "{env}.{domain}.{dataset}.sink.{layer}.{system}.{index}"
    )

    md = build_naming_lint_markdown([issue])
    assert "stage.acme.acme_configuration.sink.ods.iceberg.0" in md
    assert "stage.acme.acme_configuration.sink.raw.iceberg.0" in md


def test_naming_lint_requires_layer_for_clickhouse_sink(tmp_path: Path) -> None:
    repo_root = tmp_path
    naming = _naming_cfg()

    p = (
        repo_root
        / "acme/sink/clickhouse/connector_acme__events/stage.acme.events.sink.raw.clickhouse.0.json"
    )
    _write_json(
        p,
        {
            "name": "stage.acme.events.sink.raw.clickhouse.0",
            "config": {
                "connector.class": "com.clickhouse.kafka.connect.ClickHouseSinkConnector",
                "topics": "acme.events",
                "topic2TableMap": "acme.events=events_raw",
            },
        },
    )

    r = _renderer(repo_root)
    rr = r.render(p)

    wrong_name = "stage.acme.events.sink.clickhouse.0"
    cfg = dict(rr.manifest.config)
    cfg["name"] = wrong_name
    bad = replace(rr.manifest, name=wrong_name, config=cfg)

    issue = lint_strict_naming(bad, naming=naming)
    assert issue is not None
    assert issue.suggested_name == "stage.acme.events.sink.raw.clickhouse.0"
