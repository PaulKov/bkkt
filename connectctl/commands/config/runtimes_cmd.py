from __future__ import annotations

import argparse

from ...cli_helpers.config_scope_args import add_config_scope_args
from ...cli_helpers.output_args import add_output_format_args
from ...logging_utils import get_logger
from ...services.config.runtimes_service import ConfigRuntimesService


def cmd_config_runtimes_list(args: argparse.Namespace, *, ctx, logger=None) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    return int(ConfigRuntimesService(ctx=ctx, logger=log).list(args))


def cmd_config_runtimes_explain(args: argparse.Namespace, *, ctx, logger=None) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    return int(ConfigRuntimesService(ctx=ctx, logger=log).explain(args))


def cmd_config_runtimes_check(args: argparse.Namespace, *, ctx, logger=None) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    return int(ConfigRuntimesService(ctx=ctx, logger=log).check(args))


def build_parser(
    config_sub: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    return config_sub.add_parser(
        "runtimes",
        help="Kafka Connect runtime inventory and validation",
    )


def register_list_parser(
    runtimes_sub: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = runtimes_sub.add_parser("list", help="List configured Connect runtimes")
    add_config_scope_args(p)
    add_output_format_args(p)
    p.set_defaults(func=cmd_config_runtimes_list)
    return p


def register_explain_parser(
    runtimes_sub: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = runtimes_sub.add_parser("explain", help="Explain one Connect runtime scope")
    add_config_scope_args(p)
    add_output_format_args(p)
    p.set_defaults(func=cmd_config_runtimes_explain)
    return p


def register_check_parser(
    runtimes_sub: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = runtimes_sub.add_parser(
        "check", help="Run static checks for configured Connect runtimes"
    )
    add_config_scope_args(p)
    add_output_format_args(p)
    p.set_defaults(func=cmd_config_runtimes_check)
    return p
