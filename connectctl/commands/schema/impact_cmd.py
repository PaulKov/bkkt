from __future__ import annotations

import argparse

from ...services.schema_registry import SchemaRegistryService
from .common import add_common_readonly_args


def cmd_schema_impact(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return SchemaRegistryService(ctx=ctx, logger=logger).run_impact(args)


def register_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "impact",
        help="Infer topic/search impact for a Schema Registry subject",
    )
    add_common_readonly_args(parser)
    parser.add_argument("subject", help="Schema Registry subject")
    parser.set_defaults(func=cmd_schema_impact)
    return parser
