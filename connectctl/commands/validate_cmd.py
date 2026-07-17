from __future__ import annotations

import argparse

from ..app.context import CliContext
from ..logging_utils import get_logger
from ..services.validate_service import ValidateService
from .validate.parser import register_parser as _register_validate_parser


def cmd_validate(
    args: argparse.Namespace, *, ctx: CliContext | None = None, logger=None
) -> int:
    """CLI adapter for `connectctl validate`."""

    if ctx is None:
        ctx = CliContext.from_args(args, logger=get_logger(logger))

    svc = ValidateService(ctx=ctx, logger=logger)
    return int(svc.run(args))


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return _register_validate_parser(subparsers, handler=cmd_validate)
