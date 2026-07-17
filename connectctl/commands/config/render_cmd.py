from __future__ import annotations

import argparse

from ...cli_helpers.output_args import add_output_format_args
from ...logging_utils import get_logger
from ...output import OutputFormat
from ...services.config.render_service import ConfigRenderService


def cmd_config_render(args: argparse.Namespace, *, ctx, logger=None) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    svc = ConfigRenderService(ctx=ctx, logger=log)
    return int(svc.run(args))


def register_parser(config_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = config_sub.add_parser(
        "render",
        help="Вывести финальный connectctl.yaml (после from_cluster_group_env и env var подстановок)",
    )
    p.add_argument(
        "--cluster-group",
        action="append",
        default=None,
        help=(
            "Фильтр по cluster group (можно несколько раз или через запятую). "
            "По умолчанию: все группы из connectctl.yaml"
        ),
    )
    p.add_argument(
        "--env",
        action="append",
        default=None,
        help=(
            "Фильтр по окружению (dev|stage|prod). "
            "Можно несколько раз или через запятую. По умолчанию: все env в каждой группе"
        ),
    )
    p.add_argument(
        "--show-secrets",
        action="store_true",
        help="Показывать секреты (не маскировать значения по ключам password/token/secret/...).",
    )

    add_output_format_args(p, default=OutputFormat.yaml)

    p.add_argument(
        "--output-file",
        dest="output_file",
        help="(опционально) Записать результат в файл в том же формате, что и stdout",
    )
    p.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Не спрашивать подтверждение для широкого текстового render",
    )
    p.set_defaults(func=cmd_config_render)
    return p
