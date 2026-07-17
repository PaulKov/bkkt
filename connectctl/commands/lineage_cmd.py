from __future__ import annotations

import argparse

from ..services.operator.lineage import LineageService
from .operator_common import add_operator_output_arg, add_operator_scope_args


def cmd_lineage(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return LineageService(ctx=ctx, logger=logger).run(args)


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "lineage",
        help="Build a source/topic/sink/table lineage graph for an object",
    )
    add_operator_scope_args(parser, default_source="repo")
    add_operator_output_arg(
        parser,
        choices=("text", "json", "yaml", "markdown", "mermaid"),
        default="text",
    )
    parser.set_defaults(func=cmd_lineage)
    return parser
