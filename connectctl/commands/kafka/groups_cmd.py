from __future__ import annotations

import argparse

from ...services.kafka_admin import KafkaAdminService
from .common import add_common_readonly_args, add_limit_filter_args


def cmd_kafka_groups_list(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return KafkaAdminService(ctx=ctx, logger=logger).run_groups_list(args)


def cmd_kafka_groups_describe(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return KafkaAdminService(ctx=ctx, logger=logger).run_groups_describe(args)


def cmd_kafka_groups_lag(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return KafkaAdminService(ctx=ctx, logger=logger).run_groups_lag(args)


def build_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return subparsers.add_parser("groups", help="Kafka consumer groups inventory")


def register_list_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("list", help="List Kafka consumer groups")
    add_common_readonly_args(parser)
    add_limit_filter_args(parser)
    parser.set_defaults(func=cmd_kafka_groups_list)
    return parser


def register_describe_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("describe", help="Describe one Kafka consumer group")
    add_common_readonly_args(parser)
    parser.add_argument("group", help="Consumer group id")
    parser.add_argument(
        "--topic", default=None, help="Optional comma-separated topic filter"
    )
    parser.set_defaults(func=cmd_kafka_groups_describe)
    return parser


def register_lag_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("lag", help="Show lag for one Kafka consumer group")
    add_common_readonly_args(parser)
    parser.add_argument("group", help="Consumer group id")
    parser.add_argument(
        "--topic", default=None, help="Optional comma-separated topic filter"
    )
    parser.set_defaults(func=cmd_kafka_groups_lag)
    return parser
