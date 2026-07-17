from __future__ import annotations

import argparse
from typing import Callable

from ...cli_helpers.output_args import add_output_format_args
from ...cli_helpers.safety_help import policies_disable_help, strict_naming_disable_help


def register_parser(
    subparsers: argparse._SubParsersAction,
    *,
    handler: Callable[[argparse.Namespace], int],
) -> argparse.ArgumentParser:
    s = subparsers.add_parser(
        "compare",
        help="Сравнить один rendered manifest с live-коннектором или внешним config-файлом",
    )
    s.add_argument(
        "path",
        help="Путь к <env>.*.json манифесту (relative to repo root)",
    )
    s.add_argument(
        "--against",
        choices=["live", "connector", "file"],
        default="live",
        help="Источник actual-конфига для сравнения (default: live)",
    )
    s.add_argument(
        "--name",
        default=None,
        help="Имя live-коннектора для --against connector",
    )
    s.add_argument(
        "--file",
        default=None,
        help="Путь к JSON/YAML config-файлу для --against file",
    )
    add_output_format_args(s)
    s.add_argument(
        "--show-vars",
        dest="show_vars",
        action="store_true",
        default=True,
        help="Печатать provenance vars (default: включено)",
    )
    s.add_argument(
        "--no-show-vars",
        dest="show_vars",
        action="store_false",
        help="Отключить вывод provenance vars",
    )
    s.add_argument(
        "--vars",
        action="append",
        default=None,
        help="dbt-style vars JSON (object). Можно повторять; мерджится, побеждает последнее значение.",
    )
    s.add_argument(
        "--vars-file",
        action="append",
        default=None,
        help="Путь к JSON/YAML vars (object). Можно повторять; мерджится. Перебивается --vars.",
    )
    s.add_argument(
        "--vars-profile",
        action="append",
        default=None,
        help="Имя профиля из bkkt/vars/profiles/*.yaml. Можно повторять.",
    )
    s.add_argument(
        "--no-reuse-overrides",
        dest="reuse_overrides",
        action="store_false",
        default=True,
        help="Не применять repo-wide overrides (использовать только base.*.json + env manifest).",
    )
    s.add_argument(
        "--reuse-from",
        dest="reuse_from",
        action="append",
        default=None,
        help="Ограничить набор override-файлов, которые учитываем при render. Можно повторять.",
    )
    s.add_argument(
        "--cluster",
        default=None,
        help="(опционально) Переопределить cluster group (routing + cluster render policy)",
    )
    s.add_argument(
        "--suppress-tag-conflicts",
        action="store_true",
        help="(опционально) Подавить конфликты тегов при routing",
    )
    s.add_argument(
        "--explain-routing",
        action="store_true",
        help="Показать, как выбран target cluster",
    )
    s.add_argument(
        "--no-strict-naming",
        dest="strict_naming",
        action="store_false",
        default=True,
        help=strict_naming_disable_help(),
    )
    s.add_argument(
        "--no-policies",
        dest="policies",
        action="store_false",
        default=True,
        help=policies_disable_help(),
    )
    s.set_defaults(func=handler)
    return s
