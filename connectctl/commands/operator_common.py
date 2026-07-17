from __future__ import annotations

import argparse

from ..cli_helpers.concurrency_args import add_concurrency_args


def add_operator_scope_args(
    parser: argparse.ArgumentParser,
    *,
    default_source: str = "repo",
    include_kind: bool = True,
) -> None:
    parser.add_argument(
        "object", help="Connector name, topic, table, database or regex object"
    )
    parser.add_argument(
        "--source",
        choices=["repo", "live", "both"],
        default=default_source,
        help="Discovery source: repo, live or both",
    )
    parser.add_argument(
        "--env",
        default="all",
        help="Environment scope: dev|stage|prod|all (default: all)",
    )
    parser.add_argument(
        "--cluster",
        default="all",
        help="Cluster group scope: <name>|all (default: all)",
    )
    parser.add_argument(
        "--ignore-case", action="store_true", help="Case-insensitive matching"
    )
    parser.add_argument(
        "--limit", type=int, default=50, help="Maximum matched connectors"
    )
    if include_kind:
        parser.add_argument(
            "--kind",
            choices=[
                "auto",
                "connector",
                "topic",
                "table",
                "database",
                "regex",
                "object",
                "topic_or_table",
            ],
            default="auto",
            help="Optional object kind hint",
        )
    add_concurrency_args(parser, default_jobs=8)


def add_operator_output_arg(
    parser: argparse.ArgumentParser,
    *,
    choices: tuple[str, ...] = ("text", "json", "yaml", "markdown"),
    default: str = "text",
) -> None:
    parser.add_argument(
        "--output",
        choices=choices,
        default=default,
        help=f"Output format: {'|'.join(choices)}",
    )


__all__ = ["add_operator_output_arg", "add_operator_scope_args"]
