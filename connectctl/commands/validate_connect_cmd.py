from __future__ import annotations

import argparse

from ..app.context import CliContext
from ..logging_utils import get_logger
from ..services.validate_connect_service import ValidateConnectService
from .validate_connect.parser import register_parser as _register_parser


def cmd_validate_connect(
    args: argparse.Namespace, *, ctx: CliContext | None = None, logger=None
) -> int:
    if ctx is None:
        ctx = CliContext.from_args(args, logger=get_logger(logger))
    svc = ValidateConnectService(ctx=ctx, logger=logger)
    return int(svc.run(args))


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return _register_parser(subparsers, handler=cmd_validate_connect)
