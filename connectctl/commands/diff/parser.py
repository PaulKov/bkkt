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
    """Зарегистрировать парсер команды `connectctl diff`.

    Команда сравнивает "желаемую" конфигурацию (render манифестов) с "живой"
    конфигурацией, полученной из Kafka Connect REST.

    В multi-cluster режиме (routing) diff вычисляет целевой кластер **для каждого
    коннектора отдельно** и сравнивает с live конфигом именно в этом кластере.

    Может ограничивать сравнение файлами, затронутыми выбранным git diff.
    """

    s = subparsers.add_parser(
        "diff", help="Сравнение desired (render) конфига с live Kafka Connect"
    )
    s.add_argument("--env", required=True, help="Окружение (dev|stage|prod)")
    s.add_argument(
        "--cluster",
        default=None,
        help=(
            "Имя группы кластеров (cluster group). "
            "Если задано — принудительно использовать этот кластер для всех коннекторов. "
            "Если не задано — кластер выбирается через routing (connectctl.cluster/tags/default_cluster)."
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
        help="Diff только коннекторы, затронутые git diff",
    )
    s.add_argument("--base", help="Base git sha (по умолчанию: auto)")
    s.add_argument("--head", help="Head git sha (по умолчанию: HEAD)")
    s.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Возвращать ненулевой exit code, если найден drift",
    )
    s.add_argument(
        "--max-lines",
        type=int,
        default=200,
        help="Максимум строк diff на коннектор в отчёте (default: 200)",
    )
    add_output_format_args(s)
    s.add_argument(
        "--show-vars",
        dest="show_vars",
        action="store_true",
        default=True,
        help="Печатать provenance vars на коннектор (default: включено)",
    )
    s.add_argument(
        "--no-show-vars",
        dest="show_vars",
        action="store_false",
        help="Отключить вывод provenance vars",
    )

    # Safety validations (enabled by default)
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

    s.add_argument(
        "paths",
        nargs="*",
        help="Явные manifest paths для diff (если не указано и нет --changed, diff по всему env)",
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
