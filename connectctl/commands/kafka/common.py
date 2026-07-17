from __future__ import annotations

import argparse

from ...cli_helpers.output_args import add_output_format_args


def add_kafka_scope_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--env", required=True, help="Target env: dev|stage|prod")
    parser.add_argument(
        "--cluster",
        default=None,
        help="Cluster group. Defaults to default_cluster from connectctl.yaml",
    )
    parser.add_argument(
        "--bootstrap-server",
        default=None,
        help=(
            "Explicit Kafka bootstrap override for admin diagnostics. "
            "Comma-separated values are accepted."
        ),
    )


def add_limit_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prefix", default=None, help="Filter names by prefix")
    parser.add_argument("--regexp", default=None, help="Filter names by regex")
    parser.add_argument("--limit", type=int, default=500, help="Max rows, default: 500")


def add_common_readonly_args(parser: argparse.ArgumentParser) -> None:
    add_kafka_scope_args(parser)
    add_output_format_args(parser)
