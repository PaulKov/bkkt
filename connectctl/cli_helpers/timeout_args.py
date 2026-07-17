from __future__ import annotations

import argparse
from typing import Any


def add_wait_timeout_seconds_args(
    parser: argparse.ArgumentParser,
    *,
    default: float = 300.0,
    timeout_help: str,
    alias_help: str = "Alias for --timeout-seconds",
) -> None:
    """Register canonical timeout option plus the operator-friendly alias.

    The alias must use ``argparse.SUPPRESS`` as its default. Otherwise argparse
    stores ``None`` for ``timeout_seconds`` when the alias is omitted and
    overwrites the canonical ``--timeout-seconds`` default.
    """

    parser.add_argument(
        "--wait-timeout-seconds",
        dest="timeout_seconds",
        type=float,
        default=argparse.SUPPRESS,
        help=alias_help,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=default,
        help=timeout_help,
    )


def timeout_seconds_from_args(args: Any, *, default: float) -> float:
    """Return a float timeout while treating omitted argparse aliases as default.

    This keeps service-layer code resilient when commands are invoked from tests,
    plugin adapters, or older wrappers that may pass ``timeout_seconds=None``.
    """

    raw = getattr(args, "timeout_seconds", default)
    if raw is None:
        return float(default)
    return float(raw)
