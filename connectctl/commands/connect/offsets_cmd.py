from __future__ import annotations

import argparse
from typing import Any, Mapping

from ...cli_helpers.output_args import add_output_format_args
from ...cli_support import _read_raw_json
from ...exceptions import ConfigError
from ...logging_utils import get_logger
from ...output import OutputFormat, resolve_output_format, write_payload
from .common import (
    add_runtime_break_glass_arg,
    add_target_args,
    enforce_runtime_mutation_guard,
    resolve_target,
)


def _read_offsets_payload(src: str) -> Mapping[str, Any]:
    payload = _read_raw_json(src)
    if not isinstance(payload, dict):
        raise ConfigError("Offsets PATCH payload must be a JSON object")
    if "offsets" not in payload:
        raise ConfigError("Offsets PATCH payload must contain top-level key: offsets")
    return payload


def _print_offsets_text(log, *, name: str, payload: Mapping[str, Any]) -> None:
    offsets = payload.get("offsets")
    count = len(offsets) if isinstance(offsets, list) else "unknown"
    log.info("Connector offsets: %s", name)
    log.info("Offsets entries: %s", count)
    log.info("%s", payload)


def cmd_connect_offsets_get(args: argparse.Namespace, *, ctx, logger=None) -> int:
    """Read Kafka Connect framework-managed connector offsets."""

    log = get_logger(logger or getattr(ctx, "logger", None))
    target = resolve_target(ctx, args, logger=log)
    name = str(getattr(args, "name", "") or "").strip()
    if not name:
        raise ConfigError("--name is required")

    payload = target.client.get_offsets(name)
    fmt = resolve_output_format(args, default=OutputFormat.json)
    if fmt == OutputFormat.text:
        _print_offsets_text(log, name=name, payload=payload)
        return 0

    write_payload(
        {
            "cluster": target.cluster.name,
            "env": target.env.value,
            "name": name,
            "offsets": payload,
        },
        fmt=fmt,
    )
    return 0


def cmd_connect_offsets_patch(args: argparse.Namespace, *, ctx, logger=None) -> int:
    """Alter Kafka Connect framework-managed connector offsets."""

    log = get_logger(logger or getattr(ctx, "logger", None))
    target = resolve_target(ctx, args, logger=log)
    name = str(getattr(args, "name", "") or "").strip()
    if not name:
        raise ConfigError("--name is required")

    payload = _read_offsets_payload(str(getattr(args, "json_file", "") or ""))
    dry_run = bool(getattr(args, "dry_run", False))
    yes = bool(getattr(args, "yes", False))

    before: Mapping[str, Any] | None = None
    try:
        before = target.client.get_offsets(name)
        before_count = len(before.get("offsets", [])) if isinstance(before, dict) else 0
        log.info("Current offsets entries before PATCH: %s", before_count)
    except Exception as e:
        log.warning("Could not read current offsets before PATCH: %s", e)

    patch_count = (
        len(payload.get("offsets", []))
        if isinstance(payload.get("offsets"), list)
        else 0
    )
    log.info("Offsets PATCH target: %s entries=%s", name, patch_count)
    log.info(
        "Rollback hint: save `bkkt connect offsets get --name %s --output json` before live PATCH.",
        name,
    )

    if dry_run:
        log.info("[DRY-RUN] Would PATCH /connectors/%s/offsets", name)
        return 0

    if not yes:
        raise ConfigError(
            "Refusing to PATCH live connector offsets without --yes. "
            "Run with --dry-run first, then repeat with --yes when the payload is verified."
        )

    enforce_runtime_mutation_guard(
        ctx, args, command="connect offsets patch", dry_run=dry_run
    )
    result = target.client.patch_offsets(name, payload)
    log.info("Offsets PATCH sent for connector: %s", name)
    if result:
        log.info("Kafka Connect response: %s", result)
    return 0


def build_parser(connect_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return connect_sub.add_parser(
        "offsets",
        help="Read/patch Kafka Connect framework-managed connector offsets",
    )


def register_get_parser(
    offsets_sub: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    s = offsets_sub.add_parser("get", help="Read connector offsets")
    add_target_args(s)
    add_output_format_args(s, default=OutputFormat.json)
    s.add_argument("--name", required=True, help="Connector name")
    s.set_defaults(func=cmd_connect_offsets_get)
    return s


def register_patch_parser(
    offsets_sub: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    s = offsets_sub.add_parser("patch", help="Patch connector offsets")
    add_target_args(s)
    s.add_argument("--name", required=True, help="Connector name")
    s.add_argument(
        "--json-file",
        required=True,
        help="Path to Kafka Connect offsets PATCH JSON payload",
    )
    s.add_argument("--dry-run", action="store_true", help="Show plan without PATCH")
    add_runtime_break_glass_arg(s)
    s.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Required confirmation for live offsets PATCH",
    )
    s.set_defaults(func=cmd_connect_offsets_patch)
    return s


def register_parser(connect_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p_offsets = build_parser(connect_sub)
    offsets_sub = p_offsets.add_subparsers(dest="offsets_cmd", required=True)
    register_get_parser(offsets_sub)
    register_patch_parser(offsets_sub)
    return p_offsets
