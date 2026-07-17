from __future__ import annotations

import argparse

from ..app.context import CliContext
from ..logging_utils import get_logger
from ..services.drift_service import DriftService
from .drift.parser import register_parser as _register_drift_parser


def cmd_drift(
    args: argparse.Namespace, *, ctx: CliContext | None = None, logger=None
) -> int:
    """CLI adapter for `connectctl drift`."""

    if ctx is None:
        ctx = CliContext.from_args(args, logger=get_logger(logger))

    svc = DriftService(ctx=ctx, logger=logger)
    return int(svc.run(args))


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return _register_drift_parser(subparsers, handler=cmd_drift)
