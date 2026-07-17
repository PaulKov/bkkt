from __future__ import annotations

import argparse

from ...cli_helpers.concurrency_args import add_concurrency_args
from .common import (
    add_yes_arg,
    add_selector_args,
    add_runtime_break_glass_arg,
    add_target_args,
)
from .simple_mutation import run_simple_connector_mutation


def cmd_connect_stop(args: argparse.Namespace, *, ctx, logger=None) -> int:
    """Stop коннекторов (по фильтру), если ваш Kafka Connect поддерживает endpoint /stop."""

    return run_simple_connector_mutation(
        args=args,
        ctx=ctx,
        logger=logger,
        action_label="STOP",
        command="connect stop",
        empty_message="Нечего останавливать.",
        dry_run_message="[DRY-RUN] Would stop: %s",
        done_message="stopped: %s",
        operation=lambda connect, name: connect.stop(name),
    )


def register_parser(connect_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    s = connect_sub.add_parser(
        "stop", help="Stop коннекторы (если поддерживается /stop)"
    )
    add_target_args(s)
    add_selector_args(s, default_all=False)
    add_concurrency_args(s)
    add_runtime_break_glass_arg(s)
    add_yes_arg(s)
    s.add_argument(
        "--dry-run", action="store_true", help="Ничего не делать, только показать план"
    )
    s.set_defaults(func=cmd_connect_stop)
    return s
