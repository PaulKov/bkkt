from __future__ import annotations

import argparse

from ...services.schema_registry import SchemaRegistryService
from .common import add_common_readonly_args, add_guarded_write_args

COMPATIBILITY_MODE_CHOICES = [
    "BACKWARD",
    "BACKWARD_TRANSITIVE",
    "FORWARD",
    "FORWARD_TRANSITIVE",
    "FULL",
    "FULL_TRANSITIVE",
    "NONE",
]


def cmd_schema_compatibility_get(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return SchemaRegistryService(ctx=ctx, logger=logger).run_compatibility_get(args)


def cmd_schema_compatibility_check(
    args: argparse.Namespace, *, ctx, logger=None
) -> int:
    return SchemaRegistryService(ctx=ctx, logger=logger).run_compatibility_check(args)


def cmd_schema_compatibility_set(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return SchemaRegistryService(ctx=ctx, logger=logger).run_compatibility_set(args)


def build_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return subparsers.add_parser(
        "compatibility", help="Schema Registry compatibility checks"
    )


def register_get_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("get", help="Get global or subject compatibility")
    add_common_readonly_args(parser)
    parser.add_argument("--subject", default=None, help="Optional subject")
    parser.set_defaults(func=cmd_schema_compatibility_get)
    return parser


def register_check_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("check", help="Check schema compatibility")
    add_common_readonly_args(parser)
    parser.add_argument("subject", help="Schema Registry subject")
    parser.add_argument("--schema-file", required=True, help="Schema file to validate")
    parser.add_argument(
        "--version",
        default="latest",
        help="Version to check against, default: latest",
    )
    parser.add_argument(
        "--schema-type",
        default=None,
        type=str.upper,
        choices=["AVRO", "PROTOBUF", "JSON"],
        help="Optional schema type override",
    )
    parser.set_defaults(func=cmd_schema_compatibility_check)
    return parser


def register_set_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "set",
        help="Set global or subject compatibility with guarded dry-run/yes flow",
    )
    add_common_readonly_args(parser)
    add_guarded_write_args(parser)
    parser.add_argument("--subject", default=None, help="Optional subject")
    parser.add_argument(
        "--mode",
        required=True,
        type=str.upper,
        choices=COMPATIBILITY_MODE_CHOICES,
        help="Desired compatibility mode",
    )
    parser.set_defaults(func=cmd_schema_compatibility_set)
    return parser
