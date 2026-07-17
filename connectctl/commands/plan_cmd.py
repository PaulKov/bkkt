from __future__ import annotations

import argparse

from ..app.context import CliContext
from ..logging_utils import get_logger
from ..services.plan_service import PlanService
from .plan.parser import register_parser as _register_plan_parser


def cmd_plan(
    args: argparse.Namespace, *, ctx: CliContext | None = None, logger=None
) -> int:
    if ctx is None:
        ctx = CliContext.from_args(args, logger=get_logger(logger))
    svc = PlanService(ctx=ctx, logger=logger)
    return int(svc.run(args))


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return _register_plan_parser(subparsers, handler=cmd_plan)
