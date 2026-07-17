from __future__ import annotations

import argparse


def add_guarded_repo_write_args(parser: argparse.ArgumentParser) -> None:
    """Add standard GitOps-safe mutation flags for repo file writes."""

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ничего не записывать, только показать план и diff",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Подтвердить запись изменений в repo config",
    )
