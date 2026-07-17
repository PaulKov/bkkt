from __future__ import annotations

import argparse

from ...services.demo import DemoScaffoldService


def cmd_demo_init(args: argparse.Namespace, *, ctx, logger=None) -> int:
    _ = ctx, logger
    return DemoScaffoldService().run_init(args)


def register_parser(demo_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = demo_sub.add_parser(
        "init",
        help="Copy the bundled local Kafka/Connect/Schema Registry demo scaffold",
    )
    parser.add_argument(
        "--output-dir",
        default="bkkt-demo",
        help="Directory where demo files will be written. Default: bkkt-demo.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing demo files. By default existing files are skipped.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which files would be written without touching the filesystem.",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json", "yaml"],
        default="text",
        help="Output format. Default: text.",
    )
    parser.set_defaults(func=cmd_demo_init, requires_config=False)
    return parser
