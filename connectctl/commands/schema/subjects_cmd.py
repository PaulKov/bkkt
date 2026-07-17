from __future__ import annotations

import argparse

from ...services.schema_registry import SchemaRegistryService
from .common import add_common_readonly_args, add_limit_filter_args


def cmd_schema_subjects_list(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return SchemaRegistryService(ctx=ctx, logger=logger).run_subjects_list(args)


def cmd_schema_subjects_versions(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return SchemaRegistryService(ctx=ctx, logger=logger).run_subjects_versions(args)


def cmd_schema_subjects_describe(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return SchemaRegistryService(ctx=ctx, logger=logger).run_subjects_describe(args)


def cmd_schema_subjects_diff(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return SchemaRegistryService(ctx=ctx, logger=logger).run_subjects_diff(args)


def build_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return subparsers.add_parser("subjects", help="Schema Registry subjects")


def register_list_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("list", help="List Schema Registry subjects")
    add_common_readonly_args(parser)
    add_limit_filter_args(parser)
    parser.set_defaults(func=cmd_schema_subjects_list)
    return parser


def register_versions_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("versions", help="List subject versions")
    add_common_readonly_args(parser)
    parser.add_argument("subject", help="Schema Registry subject")
    parser.set_defaults(func=cmd_schema_subjects_versions)
    return parser


def register_describe_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("describe", help="Describe a subject or version")
    add_common_readonly_args(parser)
    parser.add_argument("subject", help="Schema Registry subject")
    parser.add_argument(
        "--version",
        default=None,
        help="Optional version to fetch, default: subject summary with latest",
    )
    parser.set_defaults(func=cmd_schema_subjects_describe)
    return parser


def register_diff_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("diff", help="Diff two subject versions")
    add_common_readonly_args(parser)
    parser.add_argument("subject", help="Schema Registry subject")
    parser.add_argument("--from-version", required=True, help="Base schema version")
    parser.add_argument("--to-version", default="latest", help="Target schema version")
    parser.set_defaults(func=cmd_schema_subjects_diff)
    return parser
