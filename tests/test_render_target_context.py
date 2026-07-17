from __future__ import annotations

import json
from pathlib import Path

from connectctl.rendering.factory import build_renderer
from connectctl.settings import Settings


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def _setup_repo(tmp_path: Path) -> tuple[Settings, Path, Path, Path]:
    cfg_path = tmp_path / "connectctl.yaml"
    cfg_path.write_text(
        """
connectors_root: connectors
default_cluster: acme-main
clusters:
  acme-main:
    prod:
      connect:
        scheme: http
        port: 8083
        hosts: ["10.0.0.1"]
      render:
        vars:
          server_id_namespace: acme-main-prod-v1
  acme-source:
    prod:
      connect:
        scheme: http
        port: 8083
        hosts: ["10.0.0.2"]
      render:
        vars:
          server_id_namespace: acme-source-prod-v1
tags:
  definitions:
    to_source:
      cluster: acme-source
""",
        encoding="utf-8",
    )

    connector_dir = tmp_path / "connectors/demo/source/mariadb/connector_demo__demo"
    _write_json(
        connector_dir / "all.json",
        {
            "config": {
                "connector.class": "io.debezium.connector.mariadb.MariaDbConnector",
                "routing.echo": "${target.cluster.name}|${target.cluster.env}|${target.cluster.server_id_namespace}",
                "database.server.id": "${fn:hash_int(connector.name, mod=4294967295, salt=target.cluster.server_id_namespace)}",
            }
        },
    )
    default_path = connector_dir / "prod.demo.demo.source.mariadb.0.json"
    explicit_path = connector_dir / "prod.demo.demo.source.mariadb.1.json"
    tagged_path = connector_dir / "prod.demo.demo.source.mariadb.2.json"
    _write_json(default_path, {"config": {}})
    _write_json(explicit_path, {"connectctl": {"cluster": "acme-source"}, "config": {}})
    _write_json(tagged_path, {"connectctl": {"tags": ["to_source"]}, "config": {}})

    settings = Settings.load(cfg_path, repo_root=tmp_path)
    return settings, default_path, explicit_path, tagged_path


def test_renderer_exposes_target_cluster_vars_for_default_explicit_tag_and_cli(
    tmp_path: Path,
) -> None:
    settings, default_path, explicit_path, tagged_path = _setup_repo(tmp_path)

    default_rr = build_renderer(settings).render(default_path)
    assert default_rr.manifest.config["routing.echo"] == (
        "acme-main|prod|acme-main-prod-v1"
    )

    explicit_rr = build_renderer(settings).render(explicit_path)
    assert explicit_rr.manifest.config["routing.echo"] == (
        "acme-source|prod|acme-source-prod-v1"
    )

    tagged_rr = build_renderer(settings).render(tagged_path)
    assert tagged_rr.manifest.config["routing.echo"] == (
        "acme-source|prod|acme-source-prod-v1"
    )

    cli_rr = build_renderer(settings, routing_cli_cluster="acme-source").render(
        default_path
    )
    assert cli_rr.manifest.config["routing.echo"] == (
        "acme-source|prod|acme-source-prod-v1"
    )


def test_server_id_is_stable_per_namespace_and_differs_across_namespaces(
    tmp_path: Path,
) -> None:
    settings, default_path, _explicit_path, _tagged_path = _setup_repo(tmp_path)

    main_renderer = build_renderer(settings)
    source_renderer = build_renderer(settings, routing_cli_cluster="acme-source")

    main_rr1 = main_renderer.render(default_path)
    main_rr2 = main_renderer.render(default_path)
    source_rr = source_renderer.render(default_path)

    assert (
        main_rr1.manifest.config["database.server.id"]
        == main_rr2.manifest.config["database.server.id"]
    )
    assert (
        main_rr1.manifest.config["database.server.id"]
        != source_rr.manifest.config["database.server.id"]
    )
