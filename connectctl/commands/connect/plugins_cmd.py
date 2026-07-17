from __future__ import annotations

import argparse
from typing import Any

from ...cli_helpers.output_args import add_output_format_args
from ...cli_helpers.terminal_table import TableColumn, render_terminal_table
from ...logging_utils import get_logger
from ...output import OutputFormat, resolve_output_format, write_payload, write_text
from .common import add_target_args, resolve_target


def cmd_connect_plugins_inventory(args: argparse.Namespace, *, ctx, logger=None) -> int:
    """Return Kafka Connect connector plugin inventory for one cluster scope."""

    log = get_logger(logger or getattr(ctx, "logger", None))
    target = resolve_target(ctx, args, logger=log)
    fmt = resolve_output_format(args)
    plugins = [dict(item) for item in target.client.list_connector_plugins()]
    payload = {
        "cluster": target.cluster.name,
        "env": target.env.value,
        "runtime": target.cluster.runtime.to_payload(),
        "plugin_count": len(plugins),
        "plugins": plugins,
    }
    if fmt == OutputFormat.text:
        write_text(_render_plugins_text(payload))
        return 0
    write_payload(payload, fmt=fmt)
    return 0


def build_parser(connect_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return connect_sub.add_parser("plugins", help="Kafka Connect plugin inventory")


def register_inventory_parser(
    plugins_sub: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    s = plugins_sub.add_parser(
        "inventory",
        help="List Kafka Connect connector plugins and versions",
    )
    add_target_args(s)
    add_output_format_args(s)
    s.set_defaults(func=cmd_connect_plugins_inventory)
    return s


def _render_plugins_text(payload: dict[str, Any]) -> str:
    rows = [
        {
            "class": str(item.get("class") or item.get("connector_class") or "-"),
            "type": str(item.get("type") or "-"),
            "version": str(item.get("version") or "-"),
        }
        for item in payload["plugins"]
    ]
    return (
        "# BKKT: Kafka Connect plugins inventory\n\n"
        f"- cluster: `{payload['cluster']}` / `{payload['env']}`\n"
        f"- runtime: `{payload['runtime']['type']}`\n"
        f"- plugin_count: `{payload['plugin_count']}`\n\n"
        + render_terminal_table(
            (
                TableColumn("class", "Class", max_width=80),
                TableColumn("type", "Type", max_width=8),
                TableColumn("version", "Version", max_width=20),
            ),
            rows,
        )
        + "\n"
    )
