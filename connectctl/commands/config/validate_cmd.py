from __future__ import annotations

import argparse

from ...logging_utils import get_logger
from ...cli_helpers.output_args import add_output_format_args
from ...services.config.validate_service import ConfigValidateService


def cmd_config_validate(args: argparse.Namespace, *, ctx, logger=None) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    svc = ConfigValidateService(ctx=ctx, logger=log)
    return int(svc.run(args))


def register_parser(config_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = config_sub.add_parser(
        "validate", help="Проверить connectctl.yaml (кластера/наследование/валидность)"
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Считать предупреждения ошибками (ненулевой exit code)",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_config_validate)
    return p
