from __future__ import annotations

import argparse
from typing import Callable

from ...cli_helpers.safety_help import strict_naming_enable_help


def register_parser(
    subparsers: argparse._SubParsersAction,
    *,
    handler: Callable[[argparse.Namespace], int],
) -> argparse.ArgumentParser:
    s = subparsers.add_parser(
        "validate-connect",
        help="Валидировать отрендеренные конфиги через Kafka Connect plugin validate endpoint (без deploy)",
    )
    s.add_argument(
        "--env",
        required=True,
        help=(
            "Окружение (dev|stage|prod). "
            "В bulk-режиме с --all также поддерживается env=all."
        ),
    )
    s.add_argument(
        "--cluster",
        default=None,
        help=(
            "Имя cluster group. "
            "Без --all: если задано — принудительно валидировать коннекторы в этом кластере. "
            "С --all: cluster=all валидирует все выбранные manifests по обычному routing, "
            "cluster=<name> фильтрует только manifests, чей normal routing идёт в этот cluster group. "
            "Если не задано — кластер выбирается per-connector через routing (connectctl.cluster/tags/default_cluster). "
            "Важно: плагины могут отличаться на разных кластерах."
        ),
    )
    s.add_argument(
        "--suppress-tag-conflicts",
        action="store_true",
        help=(
            "Если несколько тегов задают один и тот же параметр разными значениями: "
            "вывести warning и взять значение последнего тега. "
            "Параметры из tags.hard_conflict_params всегда приводят к ошибке."
        ),
    )

    s.add_argument(
        "--changed",
        action="store_true",
        help="Валидировать только manifests, затронутые git diff",
    )
    s.add_argument(
        "--all",
        action="store_true",
        help="Валидировать все deployable wrapper manifests из репозитория",
    )
    s.add_argument("--base", help="Base git sha (по умолчанию: auto)")
    s.add_argument("--head", help="Head git sha (по умолчанию: auto)")
    s.add_argument(
        "--strict-naming",
        action="store_true",
        help=strict_naming_enable_help() + " (перед Connect validate)",
    )
    s.add_argument(
        "--max-errors",
        type=int,
        default=20,
        help="Максимум per-field validation errors (по умолчанию: 20)",
    )
    s.add_argument("paths", nargs="*", help="Явные manifest paths (если не --changed)")
    s.add_argument(
        "--vars",
        action="append",
        default=None,
        help="dbt-style vars JSON (object). Можно повторять; мерджится, побеждает последнее.",
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
    s.set_defaults(func=handler)
    return s
