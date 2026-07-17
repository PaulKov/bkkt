from __future__ import annotations

import argparse

from ..app.context import CliContext
from ..logging_utils import get_logger
from ..services.inspect_service import InspectService
from .inspect.parser import register_parser as _register_inspect_parser


def cmd_inspect(
    args: argparse.Namespace, *, ctx: CliContext | None = None, logger=None
) -> int:
    if ctx is None:
        ctx = CliContext.from_args(args, logger=get_logger(logger))
    svc = InspectService(ctx=ctx, logger=logger)
    return int(svc.run(args))


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return _register_inspect_parser(subparsers, handler=cmd_inspect)
