from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from ...cli_helpers.output_args import add_output_format_args
from ...models import ConnectorManifest, ConnectorPathInfo, ConnectorType, Environment
from ...output import OutputFormat, resolve_output_format, write_payload, write_text
from ...services.schema_preflight.models import PreflightDecision
from ...services.schema_preflight.service import SchemaPreflightService


def cmd_schema_preflight(args: argparse.Namespace, *, ctx, logger=None) -> int:
    manifest = _read_manifest(Path(getattr(args, "manifest_file")))
    existing_config = _read_mapping_file(Path(getattr(args, "existing_config_file")))
    candidate_schema_files = _parse_candidate_schema_files(
        getattr(args, "candidate_schema", []) or []
    )
    result = SchemaPreflightService().analyze(
        manifest=manifest,
        existing_config=existing_config,
        candidate_schema_files=candidate_schema_files,
    )
    payload = result.to_payload()
    fmt = resolve_output_format(args)
    if fmt == OutputFormat.text:
        write_text(_render_text(payload))
    else:
        write_payload(payload, fmt=fmt)
    return 2 if result.decision is PreflightDecision.block else 0


def register_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "preflight",
        help="Analyze schema-affecting connector config changes before deploy",
    )
    parser.add_argument(
        "--manifest-file",
        required=True,
        help="Rendered connector manifest JSON/YAML with name, config and optional type metadata.",
    )
    parser.add_argument(
        "--existing-config-file",
        required=True,
        help="Existing live connector config JSON/YAML.",
    )
    parser.add_argument(
        "--candidate-schema",
        action="append",
        default=[],
        metavar="SUBJECT=PATH",
        help="Optional exact candidate schema file. Can be repeated.",
    )
    add_output_format_args(parser)
    parser.set_defaults(func=cmd_schema_preflight, requires_config=False)
    return parser


def _read_manifest(path: Path) -> ConnectorManifest:
    raw = _read_mapping_file(path)
    config = raw.get("config")
    if not isinstance(config, dict):
        raise ValueError(f"Manifest must contain object field 'config': {path}")
    env = Environment.from_str(str(raw.get("env") or "prod"))
    connector_type = ConnectorType.from_str(str(raw.get("connector_type") or "source"))
    info = ConnectorPathInfo(
        path=path.resolve(),
        relpath=Path(path.name),
        domain=str(raw.get("domain") or "unknown"),
        connector_type=connector_type,
        system=str(raw.get("system") or "unknown"),
        connector_dir=str(raw.get("connector_dir") or "unknown"),
        env=env,
        remainder=path.stem,
    )
    return ConnectorManifest(
        name=str(raw.get("name") or config.get("name") or path.stem),
        config=config,
        source_path=path.resolve(),
        info=info,
    )


def _read_mapping_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(text) or {}
    else:
        payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected mapping in {path}")
    return payload


def _parse_candidate_schema_files(items: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(
                "Invalid --candidate-schema value. Expected SUBJECT=PATH, "
                f"got: {item!r}"
            )
        subject, raw_path = item.split("=", 1)
        parsed[subject.strip()] = Path(raw_path).expanduser()
    return parsed


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"Schema preflight: {payload['decision']}",
        f"- connector: {payload['connector']}",
        f"- mode: {payload['mode']}",
    ]
    risks = payload.get("risks") or []
    if risks:
        lines.append("- risks:")
        for risk in risks:
            lines.append(
                "  - {risk_id}: severity={severity}, allowed={allowed}, keys={keys}".format(
                    risk_id=risk.get("risk_id"),
                    severity=risk.get("severity"),
                    allowed=risk.get("allowed"),
                    keys=",".join(risk.get("changed_keys") or []),
                )
            )
    else:
        lines.append("- risks: none")
    lines.append("")
    return "\n".join(lines)
