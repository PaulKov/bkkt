from __future__ import annotations

import json
from pathlib import Path

from connectctl import cli


def test_schema_preflight_cli_reports_blocking_risks(tmp_path: Path, capsys) -> None:
    manifest_path = tmp_path / "manifest.json"
    existing_path = tmp_path / "existing.json"
    manifest_path.write_text(
        json.dumps(
            {
                "name": "prod.domain.x.source.postgres.0",
                "connector_type": "source",
                "system": "postgres",
                "env": "prod",
                "config": {
                    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                    "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
                    "value.converter.wrapper.for.nullables": "true",
                    "topic.prefix": "new.prefix",
                },
            }
        ),
        encoding="utf-8",
    )
    existing_path.write_text(
        json.dumps(
            {
                "value.converter": "io.confluent.connect.protobuf.ProtobufConverter",
                "value.converter.wrapper.for.nullables": "false",
                "topic.prefix": "old.prefix",
            }
        ),
        encoding="utf-8",
    )

    rc = cli.main(
        [
            "--repo-root",
            str(tmp_path),
            "schema",
            "preflight",
            "--manifest-file",
            str(manifest_path),
            "--existing-config-file",
            str(existing_path),
            "--output",
            "json",
        ]
    )

    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] == "block"
    assert "topic_prefix_or_subject_namespace_change" in {
        risk["risk_id"] for risk in payload["risks"]
    }
