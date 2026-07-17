from __future__ import annotations

import argparse
from typing import Callable


def register_parser(
    subparsers: argparse._SubParsersAction,
    *,
    handler: Callable[[argparse.Namespace], int],
) -> argparse.ArgumentParser:
    s = subparsers.add_parser(
        "inspect", help="Показать метаданные и routing для конкретного манифеста"
    )
    s.add_argument(
        "path", help="Путь к <env>.*.json манифесту (относительно корня репозитория)"
    )
    s.add_argument(
        "--cluster",
        default=None,
        help="Переопределить cluster group (для отладки routing). По умолчанию: по routing/default_cluster",
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
        "--show-layers", action="store_true", help="Показать список слоёв (low -> high)"
    )
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
