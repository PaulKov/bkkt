from __future__ import annotations

import argparse

from ..app.context import CliContext
from ..logging_utils import get_logger
from ..services.sync_service import SyncService
from .sync.parser import register_parser as _register_sync_parser


def cmd_sync(
    args: argparse.Namespace, *, ctx: CliContext | None = None, logger=None
) -> int:
    """CLI adapter for `connectctl sync`."""

    if ctx is None:
        ctx = CliContext.from_args(args, logger=get_logger(logger))

    svc = SyncService(ctx=ctx, logger=logger)
    return int(svc.run(args))


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return _register_sync_parser(subparsers, handler=cmd_sync)
