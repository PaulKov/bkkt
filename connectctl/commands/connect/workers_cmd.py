from __future__ import annotations

import argparse
from typing import Any

from ...cli_helpers.output_args import add_output_format_args
from ...cli_helpers.terminal_table import TableColumn, render_terminal_table
from ...logging_utils import get_logger
from ...output import OutputFormat, resolve_output_format, write_payload, write_text
from .common import add_target_args, resolve_target
from .endpoints_cmd import _diagnostic_to_payload


def cmd_connect_workers_inventory(args: argparse.Namespace, *, ctx, logger=None) -> int:
    """Return Kafka Connect worker/runtime inventory for one cluster scope."""

    log = get_logger(logger or getattr(ctx, "logger", None))
    target = resolve_target(ctx, args, logger=log)
    fmt = resolve_output_format(args)
    workers = [
        _worker_payload(_diagnostic_to_payload(item))
        for item in target.client.list_endpoint_diagnostics()
    ]
    payload = {
        "cluster": target.cluster.name,
        "env": target.env.value,
        "runtime": target.cluster.runtime.to_payload(),
        "workers": workers,
    }
    if fmt == OutputFormat.text:
        write_text(_render_workers_text(payload))
        return 0
    write_payload(payload, fmt=fmt)
    return 0


def build_parser(connect_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return connect_sub.add_parser("workers", help="Kafka Connect worker inventory")


def register_inventory_parser(
    workers_sub: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    s = workers_sub.add_parser(
        "inventory",
        help="List Kafka Connect workers/endpoints and runtime metadata",
    )
    add_target_args(s)
    add_output_format_args(s)
    s.set_defaults(func=cmd_connect_workers_inventory)
    return s


def _worker_payload(endpoint: dict[str, Any]) -> dict[str, Any]:
    checks = list(endpoint.get("checks", []) or [])
    root = next((item for item in checks if item.get("path") == "/"), None)
    return {
        "endpoint": endpoint.get("base_url"),
        "healthy": bool(endpoint.get("healthy")),
        "server_info": _server_info(root),
        "checks": checks,
    }


def _server_info(root_check: dict[str, Any] | None) -> dict[str, Any] | None:
    if not root_check or root_check.get("error"):
        return None
    preview = root_check.get("response_preview")
    if not isinstance(preview, str) or not preview.strip():
        return None
    return {"raw_preview": preview}


def _render_workers_text(payload: dict[str, Any]) -> str:
    rows = [
        {
            "endpoint": str(item.get("endpoint") or "-"),
            "healthy": "yes" if item.get("healthy") else "no",
            "server": str((item.get("server_info") or {}).get("raw_preview") or "-"),
        }
        for item in payload["workers"]
    ]
    return (
        "# BKKT: Kafka Connect workers inventory\n\n"
        f"- cluster: `{payload['cluster']}` / `{payload['env']}`\n"
        f"- runtime: `{payload['runtime']['type']}`\n\n"
        + render_terminal_table(
            (
                TableColumn("endpoint", "Endpoint", max_width=42),
                TableColumn("healthy", "Healthy", max_width=7),
                TableColumn("server", "Server info", max_width=72),
            ),
            rows,
        )
        + "\n"
    )
