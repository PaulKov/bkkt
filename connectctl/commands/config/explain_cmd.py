from __future__ import annotations

import argparse

from ...logging_utils import get_logger
from ...cli_helpers.output_args import add_output_format_args
from ...services.config.explain_service import ConfigExplainService


def cmd_config_explain(args: argparse.Namespace, *, ctx, logger=None) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    svc = ConfigExplainService(ctx=ctx, logger=log)
    return int(svc.run(args))


def register_parser(config_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = config_sub.add_parser(
        "explain", help="Показать итоговый resolved config для cluster group/env"
    )
    p.add_argument(
        "--cluster-group",
        default=None,
        help="Имя cluster group (по умолчанию: default_cluster из connectctl.yaml)",
    )
    p.add_argument("--env", required=True, help="Окружение: dev|stage|prod")
    add_output_format_args(p)
    p.set_defaults(func=cmd_config_explain)
    return p
