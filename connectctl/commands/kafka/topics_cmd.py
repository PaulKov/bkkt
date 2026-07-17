from __future__ import annotations

import argparse

from ...services.kafka_admin import KafkaAdminService, KafkaTopicGitOpsService
from .common import add_common_readonly_args, add_limit_filter_args


def cmd_kafka_topics_list(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return KafkaAdminService(ctx=ctx, logger=logger).run_topics_list(args)


def cmd_kafka_topics_describe(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return KafkaAdminService(ctx=ctx, logger=logger).run_topics_describe(args)


def cmd_kafka_topics_plan(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return KafkaTopicGitOpsService(ctx=ctx, logger=logger).run_topics_plan(args)


def cmd_kafka_topics_apply(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return KafkaTopicGitOpsService(ctx=ctx, logger=logger).run_topics_apply(args)


def build_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return subparsers.add_parser("topics", help="Kafka topics inventory")


def register_list_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("list", help="List Kafka topics")
    add_common_readonly_args(parser)
    add_limit_filter_args(parser)
    parser.add_argument(
        "--include-internal",
        action="store_true",
        help="Include internal topics such as __consumer_offsets",
    )
    parser.add_argument(
        "--with-offsets",
        action="store_true",
        help="Also calculate partition and end-offset summary for selected topics",
    )
    parser.set_defaults(func=cmd_kafka_topics_list)
    return parser


def register_describe_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("describe", help="Describe one Kafka topic")
    add_common_readonly_args(parser)
    parser.add_argument("topic", help="Topic name")
    parser.add_argument(
        "--no-offsets",
        action="store_true",
        help="Skip beginning/end offset lookup",
    )
    parser.set_defaults(func=cmd_kafka_topics_describe)
    return parser


def register_plan_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("plan", help="Plan Kafka topic GitOps changes")
    add_common_readonly_args(parser)
    _add_topic_manifest_args(parser)
    parser.set_defaults(func=cmd_kafka_topics_plan)
    return parser


def register_apply_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("apply", help="Apply Kafka topic GitOps changes")
    add_common_readonly_args(parser)
    _add_topic_manifest_args(parser)
    parser.add_argument("--dry-run", action="store_true", help="Only print the plan")
    parser.add_argument(
        "--yes", "-y", action="store_true", help="Confirm live mutation"
    )
    parser.set_defaults(func=cmd_kafka_topics_apply)
    return parser


def _add_topic_manifest_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--file",
        action="append",
        required=True,
        help="Kafka topic manifest file or directory; can be passed multiple times",
    )
