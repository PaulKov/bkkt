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


def cmd_connect_pause(args: argparse.Namespace, *, ctx, logger=None) -> int:
    """Pause коннекторов (по фильтру)."""

    return run_simple_connector_mutation(
        args=args,
        ctx=ctx,
        logger=logger,
        action_label="PAUSE",
        command="connect pause",
        empty_message="Нечего ставить на паузу.",
        dry_run_message="[DRY-RUN] Would pause: %s",
        done_message="paused: %s",
        operation=lambda connect, name: connect.pause(name),
    )


def register_parser(connect_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    s = connect_sub.add_parser("pause", help="Пауза коннекторов")
    add_target_args(s)
    add_selector_args(s, default_all=False)
    add_concurrency_args(s)
    add_runtime_break_glass_arg(s)
    add_yes_arg(s)
    s.add_argument(
        "--dry-run", action="store_true", help="Ничего не делать, только показать план"
    )
    s.set_defaults(func=cmd_connect_pause)
    return s
