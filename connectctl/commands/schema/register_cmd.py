from __future__ import annotations

import argparse

from ...services.schema_registry import SchemaRegistryService
from .common import add_common_readonly_args, add_guarded_write_args


def cmd_schema_register(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return SchemaRegistryService(ctx=ctx, logger=logger).run_register(args)


def register_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "register",
        help="Register a new schema version with guarded dry-run/yes flow",
    )
    add_common_readonly_args(parser)
    add_guarded_write_args(parser)
    parser.add_argument("subject", help="Schema Registry subject")
    parser.add_argument("--schema-file", required=True, help="Schema file to register")
    parser.add_argument(
        "--schema-type",
        required=True,
        type=str.upper,
        choices=["AVRO", "PROTOBUF", "JSON"],
        help="Schema type",
    )
    parser.add_argument(
        "--version",
        default="latest",
        help="Compatibility version used for preflight, default: latest",
    )
    parser.set_defaults(func=cmd_schema_register)
    return parser
