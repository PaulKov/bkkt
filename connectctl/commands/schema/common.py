from __future__ import annotations

import argparse

from ...cli_helpers.output_args import add_output_format_args


def add_schema_scope_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--env", required=True, help="Target env: dev|stage|prod")
    parser.add_argument(
        "--cluster",
        default=None,
        help="Cluster group. Defaults to default_cluster from connectctl.yaml",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Override Schema Registry URL(s), comma-separated",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help="Schema Registry request timeout, default: config value or 10",
    )


def add_limit_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prefix", default=None, help="Filter subjects by prefix")
    parser.add_argument("--regexp", default=None, help="Filter subjects by regex")
    parser.add_argument("--limit", type=int, default=500, help="Max rows, default: 500")


def add_common_readonly_args(parser: argparse.ArgumentParser) -> None:
    add_schema_scope_args(parser)
    add_output_format_args(parser)


def add_guarded_write_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the mutation plan without changing Schema Registry",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Confirm the live Schema Registry mutation",
    )
