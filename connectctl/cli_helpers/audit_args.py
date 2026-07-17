from __future__ import annotations

import argparse


def add_audit_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--state-db",
        help="Path to BKKT SQLite state DB. Defaults to .bkkt/state/bkkt.sqlite or BKKT_STATE_DB.",
    )
    parser.add_argument(
        "--no-audit",
        action="store_true",
        help="Disable local SQLite audit write for this command.",
    )
