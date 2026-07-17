from __future__ import annotations

import argparse
from typing import Any, Sequence

from ...cli_helpers.terminal_table import TableColumn, render_terminal_table
from ...cli_helpers.output_args import add_output_format_args
from ...logging_utils import get_logger
from ...output import OutputFormat, resolve_output_format, write_payload, write_text
from .common import add_target_args, resolve_target


def _attempt_to_payload(attempt: Any) -> dict[str, Any]:
    if hasattr(attempt, "to_dict"):
        payload = attempt.to_dict()
        if isinstance(payload, dict):
            return payload
    return {
        "base_url": getattr(attempt, "base_url", None),
        "method": getattr(attempt, "method", None),
        "path": getattr(attempt, "path", None),
        "status_code": getattr(attempt, "status_code", None),
        "elapsed_ms": getattr(attempt, "elapsed_ms", None),
        "error": getattr(attempt, "error", None),
    }


def _diagnostic_to_payload(item: Any) -> dict[str, Any]:
    if hasattr(item, "to_dict"):
        payload = item.to_dict()
        if isinstance(payload, dict):
            return payload
    checks = list(getattr(item, "checks", []) or [])
    return {
        "base_url": getattr(item, "base_url", None),
        "healthy": bool(getattr(item, "healthy", False)),
        "checks": [_attempt_to_payload(a) for a in checks],
    }


def _status_cell(check: dict[str, Any]) -> str:
    if check.get("error"):
        return "ERROR"
    code = check.get("status_code")
    return f"HTTP {code}" if code is not None else "UNKNOWN"


def _format_text(payload: Sequence[dict[str, Any]]) -> str:
    rows: list[dict[str, object]] = []
    for endpoint in payload:
        base = str(endpoint.get("base_url") or "")
        healthy = "yes" if endpoint.get("healthy") else "no"
        for check in endpoint.get("checks", []) or []:
            detail = check.get("error") or check.get("response_preview") or ""
            rows.append(
                {
                    "endpoint": base,
                    "healthy": healthy,
                    "path": check.get("path") or "-",
                    "status": _status_cell(check),
                    "latency": f"{float(check.get('elapsed_ms') or 0):.1f}",
                    "detail": str(detail).replace("\n", " ")[:180] or "-",
                }
            )
    return (
        render_terminal_table(
            (
                TableColumn("endpoint", "Endpoint", max_width=36),
                TableColumn("healthy", "Healthy", max_width=7),
                TableColumn("path", "Path", max_width=36),
                TableColumn("status", "Status", max_width=12),
                TableColumn("latency", "Latency ms", max_width=10, align="right"),
                TableColumn("detail", "Detail", max_width=64),
            ),
            rows,
        )
        + "\n"
    )


def cmd_connect_endpoints(args: argparse.Namespace, *, ctx, logger=None) -> int:
    """Inspect every configured Kafka Connect worker endpoint."""

    log = get_logger(logger or getattr(ctx, "logger", None))
    target = resolve_target(ctx, args, logger=log)
    name = str(getattr(args, "name", "") or "").strip() or None
    fmt = resolve_output_format(args)

    diagnostics = target.client.list_endpoint_diagnostics(name=name)
    payload = [_diagnostic_to_payload(d) for d in diagnostics]

    if fmt == OutputFormat.text:
        write_text(_format_text(payload))
        return 0

    write_payload(
        {
            "cluster": target.cluster.name,
            "env": target.env.value,
            "name": name,
            "endpoints": payload,
        },
        fmt=fmt,
    )
    return 0


def register_parser(connect_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    s = connect_sub.add_parser(
        "endpoints",
        help="Проверить Kafka Connect REST endpoints внутри cluster group",
    )
    add_target_args(s)
    add_output_format_args(s)
    s.add_argument(
        "--name",
        default=None,
        help="Дополнительно проверить /status и /config конкретного коннектора",
    )
    s.set_defaults(func=cmd_connect_endpoints)
    return s
