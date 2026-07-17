from __future__ import annotations

import argparse

from ...cli_helpers.output_args import add_output_format_args
from ...logging_utils import get_logger
from ...services.repo_doctor.service import RepoDoctorService


def cmd_repo_doctor(args: argparse.Namespace, *, ctx, logger=None) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    svc = RepoDoctorService(ctx=ctx, logger=log)
    return int(svc.run(args))


def register_parser(repo_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = repo_sub.add_parser(
        "doctor",
        help="Проверить структуру репозитория манифестов (наличие __global, init templates, ignore_dirs и т.д.)",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Считать warning как ошибку (exit code != 0). Полезно для CI.",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_repo_doctor)
    return p
