from __future__ import annotations

import argparse

from ..cli_helpers.concurrency_args import add_concurrency_args
from ..services.operator.reconcile import ReconcileService


def cmd_reconcile(args: argparse.Namespace, *, ctx, logger=None) -> int:
    return ReconcileService(ctx=ctx, logger=logger).run(args)


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "reconcile",
        help="Prepare live-to-Git reconciliation using BKKT export planning",
    )
    parser.add_argument("--source", choices=["live"], default="live")
    parser.add_argument("--env", required=True, help="Source environment")
    parser.add_argument("--cluster", default=None, help="Source cluster group")
    parser.add_argument(
        "--names",
        action="append",
        default=[],
        help="Connector name(s), repeatable or CSV",
    )
    parser.add_argument(
        "--regexp", default=None, help="Resolve live connector names by regex"
    )
    parser.add_argument("--domain", default=None, help="Export placement override")
    parser.add_argument("--system", default=None, help="Export placement override")
    parser.add_argument(
        "--connector-dir", default=None, help="Export placement override"
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Export raw configs without reuse-overrides minimization",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Do not write files (default unless --write is set)",
    )
    parser.add_argument(
        "--write", action="store_true", help="Write planned files into the repo"
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument(
        "--output", choices=["markdown", "json", "yaml"], default="markdown"
    )
    parser.add_argument("--ignore-case", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    add_concurrency_args(parser, default_jobs=8)
    parser.set_defaults(func=cmd_reconcile)
    return parser
