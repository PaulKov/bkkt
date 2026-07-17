from __future__ import annotations

import argparse

from ..app.context import CliContext
from ..logging_utils import get_logger
from ..services.diff_service import DiffService
from .diff.parser import register_parser as _register_diff_parser


def cmd_diff(
    args: argparse.Namespace, *, ctx: CliContext | None = None, logger=None
) -> int:
    """CLI-адаптер для `connectctl diff`.

    Вся операционная логика находится в :class:`connectctl.services.diff_service.DiffService`.
    """

    if ctx is None:
        ctx = CliContext.from_args(args, logger=get_logger(logger))

    svc = DiffService(ctx=ctx, logger=logger)
    return int(svc.run(args))


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return _register_diff_parser(subparsers, handler=cmd_diff)
