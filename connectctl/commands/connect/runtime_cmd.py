from __future__ import annotations

import argparse
from typing import Any

from ...cli_helpers.output_args import add_output_format_args
from ...cli_helpers.terminal_table import TableColumn, render_terminal_table
from ...logging_utils import get_logger
from ...output import OutputFormat, resolve_output_format, write_payload, write_text
from .common import add_target_args, resolve_target
from .endpoints_cmd import _diagnostic_to_payload


def cmd_connect_runtime_diff(args: argparse.Namespace, *, ctx, logger=None) -> int:
    """Compare configured runtime contract with reachable REST diagnostics."""

    log = get_logger(logger or getattr(ctx, "logger", None))
    target = resolve_target(ctx, args, logger=log)
    fmt = resolve_output_format(args)
    endpoints = [
        _diagnostic_to_payload(item)
        for item in target.client.list_endpoint_diagnostics()
    ]
    findings = _runtime_findings(
        runtime=target.cluster.runtime.to_payload(),
        endpoints=endpoints,
    )
    payload = {
        "cluster": target.cluster.name,
        "env": target.env.value,
        "runtime": target.cluster.runtime.to_payload(),
        "endpoint_count": len(endpoints),
        "healthy_endpoint_count": sum(1 for item in endpoints if item.get("healthy")),
        "findings": findings,
        "status": (
            "ok"
            if not any(item["severity"] == "error" for item in findings)
            else "error"
        ),
    }
    if fmt == OutputFormat.text:
        write_text(_render_diff_text(payload))
        return 0
    write_payload(payload, fmt=fmt)
    return 0 if payload["status"] == "ok" else 1


def build_parser(connect_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return connect_sub.add_parser("runtime", help="Kafka Connect runtime diagnostics")


def register_diff_parser(
    runtime_sub: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    s = runtime_sub.add_parser(
        "diff",
        help="Compare configured runtime metadata with REST diagnostics",
    )
    add_target_args(s)
    add_output_format_args(s)
    s.set_defaults(func=cmd_connect_runtime_diff)
    return s


def _runtime_findings(
    *, runtime: dict[str, Any], endpoints: list[dict[str, Any]]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    runtime_type = str(runtime.get("type") or "static_hosts")
    mutation_mode = str(runtime.get("mutation_mode") or "")
    operator_managed = bool(runtime.get("operator_managed"))
    if not endpoints:
        findings.append(
            {
                "severity": "warn",
                "code": "rest_unavailable",
                "message": "Runtime has no REST endpoints configured; REST-only diagnostics are limited.",
            }
        )
    elif not any(item.get("healthy") for item in endpoints):
        findings.append(
            {
                "severity": "error",
                "code": "rest_unhealthy",
                "message": "No configured REST endpoint responded successfully.",
            }
        )
    if operator_managed and mutation_mode != "crd":
        findings.append(
            {
                "severity": "warn",
                "code": "operator_mutation_mode_not_crd",
                "message": f"Operator-managed runtime `{runtime_type}` should normally use mutation_mode=crd.",
            }
        )
    if operator_managed:
        findings.append(
            {
                "severity": "info",
                "code": "rest_diagnostics_only",
                "message": "REST is diagnostics-only by default; live mutations require --runtime-unsafe-rest.",
            }
        )
    for limitation in runtime.get("limitations") or []:
        findings.append(
            {
                "severity": "info",
                "code": "runtime_limitation",
                "message": str(limitation),
            }
        )
    return findings


def _render_diff_text(payload: dict[str, Any]) -> str:
    rows = [
        {
            "severity": item["severity"],
            "code": item["code"],
            "message": item["message"],
        }
        for item in payload["findings"]
    ]
    if not rows:
        rows = [
            {
                "severity": "ok",
                "code": "no_findings",
                "message": "No runtime drift found.",
            }
        ]
    return (
        "# BKKT: Kafka Connect runtime diff\n\n"
        f"- cluster: `{payload['cluster']}` / `{payload['env']}`\n"
        f"- runtime: `{payload['runtime']['type']}`\n"
        f"- healthy REST endpoints: `{payload['healthy_endpoint_count']}/{payload['endpoint_count']}`\n\n"
        + render_terminal_table(
            (
                TableColumn("severity", "Severity", max_width=8),
                TableColumn("code", "Code", max_width=32),
                TableColumn("message", "Message", max_width=80),
            ),
            rows,
        )
        + "\n"
    )
