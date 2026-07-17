import json
from dataclasses import replace
from pathlib import Path

import pytest

from connectctl.exceptions import ValidationError
from connectctl.models import RepoConfig
from connectctl.rendering import ConnectorRenderer
from connectctl.repo import ConnectorRepo, LayerResolver
from connectctl.validation import validate_strict_naming


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


def test_strict_naming_passes_on_example_repo(tmp_path: Path) -> None:
    repo_root = tmp_path
    p = (
        repo_root
        / "e2e/source/file/connector_e2e__filesource/dev_source_e2e__filesource.json"
    )
    _write_json(
        p,
        {
            "name": "dev.e2e.filesource.source.file.0",
            "config": {
                "connector.class": "org.apache.kafka.connect.file.FileStreamSourceConnector",
                "tasks.max": "1",
                "file": "/tmp/e2e/source.txt",
                "topic": "e2e_source",
            },
        },
    )

    r = _renderer(repo_root)
    rr = r.render(p)
    validate_strict_naming(rr.manifest)


def test_strict_naming_fails_on_mismatched_config_name(tmp_path: Path) -> None:
    repo_root = tmp_path
    p = (
        repo_root
        / "e2e/source/file/connector_e2e__filesource/dev_source_e2e__filesource.json"
    )
    _write_json(
        p,
        {
            "name": "dev.e2e.filesource.source.file.0",
            "config": {
                "connector.class": "org.apache.kafka.connect.file.FileStreamSourceConnector",
                "tasks.max": "1",
                "file": "/tmp/e2e/source.txt",
                "topic": "e2e_source",
            },
        },
    )

    r = _renderer(repo_root)
    rr = r.render(p)

    new_cfg = dict(rr.manifest.config)
    new_cfg["name"] = "dev.some.other.name"  # wrong
    bad = replace(rr.manifest, config=new_cfg)

    with pytest.raises(ValidationError):
        validate_strict_naming(bad)
