from __future__ import annotations

import json

from connectctl.cli_parser import build_parser
from connectctl.services.demo import DemoScaffoldService, DemoSmokeService


def test_cli_parser_exposes_demo_init_without_config_requirement() -> None:
    parser = build_parser()

    args = parser.parse_args(["demo", "init", "--output-dir", "demo-out"])

    assert args.cmd == "demo"
    assert args.demo_cmd == "init"
    assert args.output_dir == "demo-out"
    assert args.requires_config is False


def test_cli_parser_exposes_demo_smoke_without_config_requirement() -> None:
    parser = build_parser()

    args = parser.parse_args(["demo", "smoke", "--output", "json"])

    assert args.cmd == "demo"
    assert args.demo_cmd == "smoke"
    assert args.requires_config is False


def test_demo_init_dry_run_does_not_write_files(tmp_path) -> None:
    output_dir = tmp_path / "demo"
    result = DemoScaffoldService().init(output_dir=output_dir, dry_run=True)

    assert result.dry_run is True
    assert not output_dir.exists()
    actions = {item.action for item in result.files}
    assert actions == {"would_create"}
    assert any(item.path == "docker-compose.yml" for item in result.files)
    assert any(item.path == "connectctl.yaml" for item in result.files)


def test_demo_init_writes_assets_and_skips_existing_files(tmp_path) -> None:
    output_dir = tmp_path / "demo"
    service = DemoScaffoldService()

    first = service.init(output_dir=output_dir)
    second = service.init(output_dir=output_dir)

    assert (output_dir / "docker-compose.yml").exists()
    assert (output_dir / "connectctl.yaml").exists()
    assert (output_dir / "kafka/topics/dev/demo.yaml").exists()
    assert {item.action for item in first.files} == {"created"}
    assert {item.action for item in second.files} == {"skipped"}


def test_demo_init_force_overwrites_existing_files(tmp_path) -> None:
    output_dir = tmp_path / "demo"
    service = DemoScaffoldService()
    service.init(output_dir=output_dir)
    target = output_dir / "connectctl.yaml"
    target.write_text("custom\n", encoding="utf-8")

    result = service.init(output_dir=output_dir, force=True)

    assert "custom" not in target.read_text(encoding="utf-8")
    assert "default_cluster: local" in target.read_text(encoding="utf-8")
    assert "overwritten" in {item.action for item in result.files}


def test_demo_init_result_has_machine_readable_payload(tmp_path) -> None:
    output_dir = tmp_path / "demo"
    result = DemoScaffoldService().init(output_dir=output_dir, dry_run=True)
    payload = result.to_dict()

    assert payload["dry_run"] is True
    assert payload["output_dir"] == str(output_dir.resolve())
    assert "docker compose up -d" in payload["next_commands"]
    # Keep the payload JSON-serializable for UI/API reuse.
    json.dumps(payload)


def test_demo_smoke_validates_generated_assets(tmp_path) -> None:
    output_dir = tmp_path / "demo-smoke"

    result = DemoSmokeService().smoke(output_dir=output_dir)

    assert result.ok is True
    assert (output_dir / "connectctl.yaml").exists()
    assert (output_dir / "docker-compose.yml").exists()
    assert {check.status for check in result.checks} == {"pass"}
    json.dumps(result.to_dict())
