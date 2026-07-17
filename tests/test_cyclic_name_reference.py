from __future__ import annotations

from pathlib import Path

import pytest

from connectctl.exceptions import RenderError
from connectctl.models import RepoConfig
from connectctl.repo.scanner import ConnectorRepo
from connectctl.repo.layers import LayerResolver
from connectctl.rendering.renderer import ConnectorRenderer


def test_name_cannot_reference_connector_name(tmp_path: Path) -> None:
    # Arrange minimal repo layout with global config.name placeholder
    (tmp_path / "__global").mkdir(parents=True)
    (tmp_path / "__global" / "all.json").write_text(
        '{"config": {"name": "${connector.name}"}}',
        encoding="utf-8",
    )

    env_file = (
        tmp_path
        / "partners"
        / "source"
        / "mariadb"
        / "connector_partners__acme_common"
        / "prod.partners.acme_common.source.mariadb.1.json"
    )
    env_file.parent.mkdir(parents=True, exist_ok=True)
    # Cyclic name reference
    env_file.write_text(
        '{"name": "${connector.name}", "vars": {"index": 1}, "config": {"snapshot.mode": "initial"}}',
        encoding="utf-8",
    )

    repo_cfg = RepoConfig(root=tmp_path, connectors_root=tmp_path)
    repo = ConnectorRepo(repo_cfg)
    layers = LayerResolver(repo_cfg)
    renderer = ConnectorRenderer(repo=repo, layers=layers)

    # Act / Assert
    with pytest.raises(RenderError) as e:
        renderer.render(env_file)

    assert "Cyclic reference detected" in str(e.value)
    assert "connector.name" in str(e.value)
