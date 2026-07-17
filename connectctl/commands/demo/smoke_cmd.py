from __future__ import annotations

import argparse

from ...services.demo import DemoSmokeService


def cmd_demo_smoke(args: argparse.Namespace, *, ctx, logger=None) -> int:
    _ = ctx, logger
    return DemoSmokeService().run(args)


def register_parser(demo_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = demo_sub.add_parser(
        "smoke",
        help="Validate bundled demo assets without requiring Docker-in-Docker",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory for generated smoke files. Default: temporary directory.",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep generated smoke files. Requires --output-dir.",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json", "yaml"],
        default="text",
        help="Output format. Default: text.",
    )
    parser.set_defaults(func=cmd_demo_smoke, requires_config=False)
    return parser
