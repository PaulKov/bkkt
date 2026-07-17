from __future__ import annotations

import argparse

from ..app.context import CliContext
from ..logging_utils import get_logger
from ..services.export_service import ExportService
from .export.parser import register_parser as _register_export_parser


def cmd_export(
    args: argparse.Namespace, *, ctx: CliContext | None = None, logger=None
) -> int:
    """CLI adapter for `bkkt export`.

    The heavy lifting lives in :class:`connectctl.services.export_service.ExportService`.
    """

    # Allow direct calls in tests/scripts.
    if ctx is None:
        ctx = CliContext.from_args(args, logger=get_logger(logger))

    svc = ExportService(ctx=ctx, logger=logger)
    return int(svc.run(args))


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = _register_export_parser(subparsers)
    # Backward compatibility: keep `func=` for scripts that still rely on args.func.
    p.set_defaults(func=cmd_export)
    return p
