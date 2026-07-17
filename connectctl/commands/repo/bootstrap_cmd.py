from __future__ import annotations

import argparse

from ...logging_utils import get_logger
from ...services.repo_bootstrap.service import RepoBootstrapService


def cmd_repo_bootstrap(args: argparse.Namespace, *, ctx, logger=None) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    svc = RepoBootstrapService(ctx=ctx, logger=log)
    return int(svc.run(args))


def register_parser(repo_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = repo_sub.add_parser(
        "bootstrap",
        help=(
            "Generate starter files for a BKKT manifests repository "
            "(connectctl.yaml, __global, __init_templates, schemas)"
        ),
    )

    p.add_argument(
        "--preset",
        choices=["full", "minimal"],
        default="full",
        help=(
            "Which starter set to create: full=copied assets from BKKT, minimal=create only lightweight placeholders. "
            "default: full"
        ),
    )
    p.add_argument(
        "--only",
        action="append",
        choices=["connectctl", "global", "init-templates", "schemas"],
        default=None,
        help=(
            "Create only selected sections. Can be specified multiple times. "
            "Default: connectctl + global + init-templates."
        ),
    )
    p.add_argument(
        "--init-templates-root",
        default=None,
        help=(
            "Where to write init templates (default: BKKT_INIT_TEMPLATES_ROOT or __init_templates). "
            "Useful when your repo stores templates in a custom path."
        ),
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files (by default existing files are skipped).",
    )
    p.add_argument(
        "--update",
        action="store_true",
        help=(
            "Safely refresh starter assets: if a file exists and differs, "
            "BKKT will NOT overwrite it and will create a neighboring *.bkkt.dist file instead. "
            "Useful after upgrading the bkkt package. Cannot be combined with --force."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the plan and write nothing.",
    )

    p.set_defaults(func=cmd_repo_bootstrap, requires_config=False)
    return p
