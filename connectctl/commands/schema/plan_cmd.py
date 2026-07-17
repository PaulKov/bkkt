from __future__ import annotations

import argparse

from ...services.schema_registry import SchemaRegistryService
from .common import add_common_readonly_args


def cmd_schema_plan(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return SchemaRegistryService(ctx=ctx, logger=logger).run_plan(args)


def register_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "plan",
        help="Plan schema evolution impact before registering a version",
    )
    add_common_readonly_args(parser)
    parser.add_argument("subject", help="Schema Registry subject")
    parser.add_argument("--schema-file", required=True, help="Candidate schema file")
    parser.add_argument(
        "--schema-type",
        required=True,
        type=str.upper,
        choices=["AVRO", "PROTOBUF", "JSON"],
        help="Candidate schema type",
    )
    parser.add_argument(
        "--version",
        default="latest",
        help="Compatibility version used for preflight, default: latest",
    )
    parser.set_defaults(func=cmd_schema_plan)
    return parser
