from __future__ import annotations

import argparse

from ...services.kafka_admin import KafkaAdminService
from .common import add_common_readonly_args


def cmd_kafka_brokers_describe(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return KafkaAdminService(ctx=ctx, logger=logger).run_brokers_describe(args)


def cmd_kafka_brokers_health(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return KafkaAdminService(ctx=ctx, logger=logger).run_brokers_health(args)


def build_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return subparsers.add_parser("brokers", help="Kafka broker and cluster inventory")


def register_describe_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("describe", help="Describe Kafka brokers")
    add_common_readonly_args(parser)
    parser.add_argument(
        "--configs",
        action="store_true",
        help="Best-effort broker config lookup",
    )
    parser.set_defaults(func=cmd_kafka_brokers_describe)
    return parser


def register_health_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "health", help="Read-only Kafka broker health summary"
    )
    add_common_readonly_args(parser)
    parser.set_defaults(func=cmd_kafka_brokers_health)
    return parser
