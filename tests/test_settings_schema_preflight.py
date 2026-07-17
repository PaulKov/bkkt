from __future__ import annotations

from pathlib import Path

from connectctl.settings_models import Settings


def test_settings_loads_schema_registry_preflight_allowlist(tmp_path: Path) -> None:
    config = tmp_path / "connectctl.yaml"
    config.write_text(
        """
clusters:
  acme-main:
    prod:
      connect:
        hosts: ["127.0.0.1:8083"]
schema_registry_preflight:
  allowlist:
    - connector: prod.domain.x.source.postgres.0
      risk_id: topic_prefix_or_subject_namespace_change
      adr: docs/adr/0001.md
      owner: data-platform
      expires_at: "2999-01-01"
      reason: V2 migration
""",
        encoding="utf-8",
    )

    settings = Settings.load(config, repo_root=tmp_path)

    assert settings.schema_registry_preflight["allowlist"][0]["risk_id"] == (
        "topic_prefix_or_subject_namespace_change"
    )
