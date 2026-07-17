from __future__ import annotations

import argparse

from ...cli_helpers.config_scope_args import add_config_scope_args
from ...cli_helpers.concurrency_args import add_concurrency_args
from ...cli_helpers.guarded_write_args import add_guarded_repo_write_args
from ...cli_helpers.output_args import add_output_format_args
from ...cli_helpers.repeatable_args import add_repeatable_csv_arg
from ...logging_utils import get_logger
from ...services.config.hosts_service import ConfigHostsService


def cmd_config_hosts_check(args: argparse.Namespace, *, ctx, logger=None) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    return int(ConfigHostsService(ctx=ctx, logger=log).check(args))


def cmd_config_hosts_add(args: argparse.Namespace, *, ctx, logger=None) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    return int(ConfigHostsService(ctx=ctx, logger=log).add(args))


def cmd_config_hosts_remove(args: argparse.Namespace, *, ctx, logger=None) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    return int(ConfigHostsService(ctx=ctx, logger=log).remove(args))


def build_parser(config_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return config_sub.add_parser(
        "hosts",
        help="Проверить/добавить/удалить Kafka Connect REST hosts в connectctl.yaml",
    )


def register_check_parser(
    hosts_sub: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = hosts_sub.add_parser("check", help="Проверить health Connect REST hosts")
    add_config_scope_args(p)
    _add_connect_host_arg(p, required=False)
    p.add_argument(
        "--timeout-seconds",
        type=float,
        default=5.0,
        help="HTTP timeout на один endpoint, по умолчанию 5 секунд",
    )
    add_concurrency_args(p, default_jobs=8)
    add_output_format_args(p)
    p.set_defaults(func=cmd_config_hosts_check)
    return p


def register_add_parser(
    hosts_sub: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = hosts_sub.add_parser("add", help="Добавить Connect REST host(s) в scope")
    add_config_scope_args(p, require_env=True, require_cluster_group=True)
    _add_connect_host_arg(p, required=True)
    p.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Не делать preflight health check перед записью host(s)",
    )
    add_guarded_repo_write_args(p)
    add_output_format_args(p)
    p.set_defaults(func=cmd_config_hosts_add)
    return p


def register_remove_parser(
    hosts_sub: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = hosts_sub.add_parser("remove", help="Удалить Connect REST host(s) из scope")
    add_config_scope_args(p, require_env=True, require_cluster_group=True)
    _add_connect_host_arg(p, required=True)
    add_guarded_repo_write_args(p)
    add_output_format_args(p)
    p.set_defaults(func=cmd_config_hosts_remove)
    return p


def _add_connect_host_arg(parser: argparse.ArgumentParser, *, required: bool) -> None:
    add_repeatable_csv_arg(
        parser,
        "--connect-host",
        "--host",
        dest="connect_host",
        help="Kafka Connect REST host/IP без scheme; можно повторять или передавать CSV",
    )
    # argparse does not support required for a helper that registers append with
    # an alias cleanly, so we enforce requiredness in the service for mutations.
    _ = required
