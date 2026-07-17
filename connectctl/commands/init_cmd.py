from __future__ import annotations

import argparse

from ..app.context import CliContext
from ..logging_utils import get_logger
from ..services.init_service import InitService
from .init.parser import register_parser as _register_init_parser


def cmd_init(
    args: argparse.Namespace, *, ctx: CliContext | None = None, logger=None
) -> int:
    """CLI adapter for `connectctl init`.

    The scaffolding logic lives in :class:`connectctl.services.init_service.InitService`.
    """

    if ctx is None:
        ctx = CliContext.from_args(args, logger=get_logger(logger))

    svc = InitService(ctx=ctx, logger=logger)
    return int(svc.run(args))


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return _register_init_parser(subparsers, handler=cmd_init)
