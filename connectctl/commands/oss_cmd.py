from __future__ import annotations

import argparse

from ..services.oss_hygiene import OssHygieneService


def build_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return subparsers.add_parser(
        "oss",
        help="OSS readiness, public-asset hygiene and v1.0 checks",
    )


def cmd_oss_hygiene(args: argparse.Namespace, *, ctx, logger=None) -> int:
    _ = ctx, logger
    return OssHygieneService().run_hygiene(args)


def cmd_oss_readiness(args: argparse.Namespace, *, ctx, logger=None) -> int:
    _ = ctx, logger
    return OssHygieneService().run_readiness(args)


def register_hygiene_parser(
    oss_sub: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = oss_sub.add_parser(
        "hygiene",
        help="Scan public assets or the full repository for secrets/internal references",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root to scan. Default: current directory.",
    )
    parser.add_argument(
        "--scope",
        choices=["public", "repository"],
        default="public",
        help="public=docs/demo assets; repository=hard-deny secret/internal scan.",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json", "yaml"],
        default="text",
        help="Output format. Default: text.",
    )
    parser.set_defaults(func=cmd_oss_hygiene, requires_config=False)
    return parser


def register_readiness_parser(
    oss_sub: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = oss_sub.add_parser(
        "readiness",
        help="Run v1.0 OSS readiness checklist checks",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root to check. Default: current directory.",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json", "yaml"],
        default="text",
        help="Output format. Default: text.",
    )
    parser.set_defaults(func=cmd_oss_readiness, requires_config=False)
    return parser
