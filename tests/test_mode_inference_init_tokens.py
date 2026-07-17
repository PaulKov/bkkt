from __future__ import annotations

import json
from pathlib import Path

from connectctl.models import RepoConfig
from connectctl.repo import ConnectorRepo, LayerResolver
from connectctl.rendering import ConnectorRenderer


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def test_mode_is_inferred_from_dot_style_name_for_init_and_initial(
    tmp_path: Path,
) -> None:
    # Minimal global layer so config gets a "name" field like in the real repo.
    _write_json(
        tmp_path / "__global/all.json", {"config": {"name": "${connector.name}"}}
    )

    cfg = RepoConfig(root=tmp_path, connectors_root=tmp_path, ignore_dirs=())
    repo = ConnectorRepo(cfg)
    renderer = ConnectorRenderer(repo=repo, layers=LayerResolver(cfg))

    for token in ["init", "initial"]:
        env_file = (
            tmp_path
            / "merchants"
            / "source"
            / "mariadb"
            / "connector_foo__dbt"
            / f"prod.merchants.foo.source.mariadb.{token}.dbt.0.json"
        )
        _write_json(
            env_file,
            {
                "config": {
                    "connector.class": "io.debezium.connector.mariadb.MariaDbConnector",
                }
            },
        )

        rr = renderer.render(env_file)

        # Both `.init.` and `.initial.` tokens should normalize to mode=init.
        assert rr.manifest.info.mode == "init"
