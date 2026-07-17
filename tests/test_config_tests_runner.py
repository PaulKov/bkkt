from __future__ import annotations

from pathlib import Path

from connectctl.models import (
    ConnectorManifest,
    ConnectorPathInfo,
    ConnectorType,
    Environment,
)
from connectctl.validation import ConfigTestRunner


def _manifest(*, config: dict[str, str]) -> ConnectorManifest:
    path = Path(
        "/tmp/connectors/partnerst/sink/iceberg/connector_partnerst__kafka/prod.partnerst.kafka.sink.raw.iceberg.0.json"
    )
    return ConnectorManifest(
        name="prod.partnerst.kafka.sink.raw.iceberg.0",
        config=config,
        source_path=path,
        info=ConnectorPathInfo(
            path=path,
            relpath=Path(
                "connectors/partnerst/sink/iceberg/connector_partnerst__kafka/prod.partnerst.kafka.sink.raw.iceberg.0.json"
            ),
            domain="partnerst",
            connector_type=ConnectorType.sink,
            system="iceberg",
            connector_dir="connector_partnerst__kafka",
            env=Environment.prod,
            remainder="raw",
            mode=None,
            variant="raw",
        ),
    )


def test_config_tests_cluster_group_selector_and_forbid_key_patterns() -> None:
    runner = ConfigTestRunner.from_settings(
        repo_root=Path("/tmp"),
        config_tests={
            "enabled": True,
            "rules": [
                {
                    "id": "forbid-foreign-kafka-on-plain-external",
                    "applies_to": {"cluster_group": ["acme-external"]},
                    "check": "forbid_key_patterns",
                    "patterns": [
                        "iceberg.kafka.*",
                        "*.override.bootstrap.servers",
                    ],
                }
            ],
        },
    )

    manifest = _manifest(
        config={
            "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
            "iceberg.kafka.bootstrap.servers": "b-1.example:9096",
        }
    )

    issues = runner.validate(manifest, context={"cluster_group": "acme-external"})
    assert [i.key for i in issues] == ["iceberg.kafka.bootstrap.servers"]

    other_cluster_issues = runner.validate(
        manifest, context={"cluster_group": "acme-external_foreign_kafka"}
    )
    assert other_cluster_issues == []


def test_config_tests_require_key_patterns_reports_missing_pattern() -> None:
    runner = ConfigTestRunner.from_settings(
        repo_root=Path("/tmp"),
        config_tests={
            "enabled": True,
            "rules": [
                {
                    "id": "require-foreign-overrides",
                    "applies_to": {"cluster_group": ["acme-external_foreign_kafka"]},
                    "check": "require_key_patterns",
                    "patterns": [
                        "iceberg.kafka.bootstrap.servers",
                        "consumer.override.bootstrap.servers",
                    ],
                }
            ],
        },
    )

    manifest = _manifest(
        config={
            "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
            "iceberg.kafka.bootstrap.servers": "b-1.example:9096",
        }
    )

    issues = runner.validate(
        manifest, context={"cluster_group": "acme-external_foreign_kafka"}
    )
    assert len(issues) == 1
    assert issues[0].key == "consumer.override.bootstrap.servers"


def test_config_tests_tags_selector_matches_any_tag() -> None:
    runner = ConfigTestRunner.from_settings(
        repo_root=Path("/tmp"),
        config_tests={
            "enabled": True,
            "rules": [
                {
                    "id": "require-foreign-bootstrap-for-tagged-connectors",
                    "applies_to": {"tags": ["external_foreign_kafka*"]},
                    "check": "require_key_patterns",
                    "patterns": ["iceberg.kafka.bootstrap.servers"],
                }
            ],
        },
    )

    manifest = _manifest(
        config={"connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector"}
    )

    issues = runner.validate(
        manifest, context={"tags": ["external_foreign_kafka", "team_x"]}
    )
    assert len(issues) == 1
    assert issues[0].key == "iceberg.kafka.bootstrap.servers"


def test_config_tests_negative_tag_selector_skips_allowlisted_connectors() -> None:
    runner = ConfigTestRunner.from_settings(
        repo_root=Path("/tmp"),
        config_tests={
            "enabled": True,
            "rules": [
                {
                    "id": "require-standard-source-key-unless-legacy-tag",
                    "applies_to": {"not_tags": ["legacy_nullable_subject"]},
                    "check": "require_keys",
                    "keys": ["value.converter.wrapper.for.nullables"],
                }
            ],
        },
    )

    manifest = _manifest(config={"connector.class": "example.SourceConnector"})

    assert runner.validate(manifest, context={"tags": []})[0].key == (
        "value.converter.wrapper.for.nullables"
    )
    assert (
        runner.validate(manifest, context={"tags": ["legacy_nullable_subject", "ops"]})
        == []
    )


def test_config_tests_auto_discovers_repo_convention_files(tmp_path: Path) -> None:
    tests_dir = tmp_path / "config_tests" / "source"
    tests_dir.mkdir(parents=True)
    (tests_dir / "b-retry.yaml").write_text(
        """
rules:
  - id: b-retry
    check: require_keys
    keys: [errors.max.retries]
""",
        encoding="utf-8",
    )
    (tests_dir / "a-nullability.yaml").write_text(
        """
rules:
  - id: a-nullability
    check: require_keys
    keys: [value.converter.wrapper.for.nullables]
""",
        encoding="utf-8",
    )

    runner = ConfigTestRunner.from_settings(repo_root=tmp_path, config_tests={})

    assert [rule["id"] for rule in runner.rules] == ["a-nullability", "b-retry"]
    assert [rule["_source"] for rule in runner.rules] == [
        "config_tests/source/a-nullability.yaml",
        "config_tests/source/b-retry.yaml",
    ]


def test_config_tests_absent_convention_dir_has_no_rules(tmp_path: Path) -> None:
    runner = ConfigTestRunner.from_settings(repo_root=tmp_path, config_tests={})

    assert runner.enabled is True
    assert runner.rules == []


def test_config_tests_explicit_files_remain_backward_compatible(tmp_path: Path) -> None:
    convention_dir = tmp_path / "config_tests"
    convention_dir.mkdir()
    (convention_dir / "convention.yaml").write_text(
        """
rules:
  - id: convention-rule
    check: require_keys
    keys: [from.convention]
""",
        encoding="utf-8",
    )
    explicit = tmp_path / "legacy-config-tests.yaml"
    explicit.write_text(
        """
rules:
  - id: explicit-rule
    check: require_keys
    keys: [from.explicit]
""",
        encoding="utf-8",
    )

    runner = ConfigTestRunner.from_settings(
        repo_root=tmp_path,
        config_tests={"enabled": True, "files": ["legacy-config-tests.yaml"]},
    )

    assert [rule["id"] for rule in runner.rules] == ["explicit-rule"]
    assert runner.rules[0]["_source"] == "legacy-config-tests.yaml"
