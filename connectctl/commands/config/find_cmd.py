from __future__ import annotations

import argparse

from ...cli_helpers.config_scope_args import add_config_scope_args
from ...cli_helpers.output_args import add_output_format_args
from ...cli_helpers.repeatable_args import add_repeatable_csv_arg
from ...logging_utils import get_logger
from ...services.config.find_service import ConfigFindService


def cmd_config_find(args: argparse.Namespace, *, ctx, logger=None) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    svc = ConfigFindService(ctx=ctx, logger=log)
    return int(svc.run(args))


def register_parser(config_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = config_sub.add_parser(
        "find",
        help="Найти cluster/env по Connect host, Kafka bootstrap или Schema Registry",
    )
    add_config_scope_args(p)
    add_repeatable_csv_arg(
        p,
        "--connect-host",
        dest="connect_host",
        help="Искать по Kafka Connect REST host/IP/host:port",
    )
    add_repeatable_csv_arg(
        p,
        "--kafka-bootstrap",
        dest="kafka_bootstrap",
        help="Искать по Kafka bootstrap host/IP/host:port",
    )
    add_repeatable_csv_arg(
        p,
        "--schema-registry-url",
        "--schema-registry",
        dest="schema_registry_url",
        help="Искать по Schema Registry URL/host/IP/host:port",
    )
    add_repeatable_csv_arg(
        p,
        "--connector",
        dest="connector",
        help="Connector name hint; connector-level lookup is delegated to bkkt search",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_config_find)
    return p
