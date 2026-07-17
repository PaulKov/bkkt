from __future__ import annotations

import argparse

from ..app.context import CliContext
from ..logging_utils import get_logger
from ..services.apply_service import ApplyService
from ..services.audit import audit_session_from_args
from .apply.parser import register_parser as _register_apply_parser


def cmd_apply(
    args: argparse.Namespace, *, ctx: CliContext | None = None, logger=None
) -> int:
    """CLI adapter for `connectctl apply`.

    The operational logic lives in :class:`connectctl.services.apply_service.ApplyService`.
    """

    # Allow direct calls in tests/scripts.
    if ctx is None:
        ctx = CliContext.from_args(args, logger=get_logger(logger))

    svc = ApplyService(ctx=ctx, logger=logger)
    with audit_session_from_args(command="apply", args=args, ctx=ctx) as audit:
        audit.event(
            "apply_requested",
            payload={
                "paths": list(getattr(args, "paths", []) or []),
                "changed": bool(getattr(args, "changed", False)),
                "dry_run": bool(getattr(args, "dry_run", False)),
            },
        )
        result = int(svc.run(args))
        audit.set_result_code(result)
    return result


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    # Delegate parser creation to avoid large command modules.
    return _register_apply_parser(subparsers, handler=cmd_apply)
