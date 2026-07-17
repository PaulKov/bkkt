from __future__ import annotations

import json
from pathlib import Path

from connectctl.models import RepoConfig
from connectctl.repo import ConnectorRepo, LayerResolver
from connectctl.rendering import ConnectorRenderer
from connectctl.validation.policies import lint_policies


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def test_policy_does_not_warn_when_mode_is_inferred_from_dot_style_name(
    tmp_path: Path,
) -> None:
    # Minimal global layer so config gets a "name" field like in the real repo.
    _write_json(
        tmp_path / "__global/all.json", {"config": {"name": "${connector.name}"}}
    )

    # connector_dir has NO cdc/init token, but dot-style name contains `.cdc.` token.
    # Mode should be inferred from the filename tokens.
    env_file = (
        tmp_path
        / "merchants"
        / "source"
        / "mariadb"
        / "connector_foo__dbt"
        / "prod.merchants.foo.source.mariadb.cdc.dbt.0.json"
    )
    _write_json(
        env_file,
        {
            # Dot-style manifest can omit "name" (inferred from filename)
            "config": {
                "connector.class": "io.debezium.connector.mariadb.MariaDbConnector",
            }
        },
    )

    cfg = RepoConfig(root=tmp_path, connectors_root=tmp_path, ignore_dirs=())
    repo = ConnectorRepo(cfg)
    renderer = ConnectorRenderer(repo=repo, layers=LayerResolver(cfg))

    rr = renderer.render(env_file)
    assert rr.manifest.info.mode == "cdc"  # inferred from filename

    issues = lint_policies(rr.manifest, env=rr.manifest.info.env, layers=rr.layers)

    assert not any(i.policy == "MODE_NOT_RECOGNIZED" for i in issues)
