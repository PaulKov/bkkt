from __future__ import annotations

import argparse
from typing import Callable

from ...cli_helpers.output_args import add_output_format_args
from ...cli_helpers.safety_help import policies_disable_help, strict_naming_disable_help
from ...models import Environment


def register_parser(
    subparsers: argparse._SubParsersAction,
    *,
    handler: Callable[[argparse.Namespace], int],
) -> argparse.ArgumentParser:
    """Register `connectctl drift` parser."""

    s = subparsers.add_parser(
        "drift",
        help="Собрать отчёт о дрейфе (repo manifests vs live Kafka Connect) для окружения",
    )
    s.add_argument(
        "--env",
        required=True,
        choices=[e.value for e in Environment],
        help="Target environment",
    )
    s.add_argument(
        "--cluster",
        default=None,
        help="Имя группы кластеров (cluster group). Если не задано — используется default_cluster.",
    )
    s.add_argument(
        "--clusters",
        nargs="?",
        const="all",
        default=None,
        help=(
            "Проверять drift по набору cluster groups без override. "
            "Укажите список через запятую или используйте --clusters all. "
            "Нельзя использовать вместе с --cluster."
        ),
    )
    s.add_argument(
        "paths",
        nargs="*",
        help="Опционально: manifest paths (repo-relative), чтобы ограничить область проверки",
    )
    s.add_argument(
        "--changed",
        action="store_true",
        help="Проверять только манифесты, затронутые git diff (base..head)",
    )
    s.add_argument("--base", help="Base git SHA для --changed (по умолчанию: auto)")
    s.add_argument("--head", help="Head git SHA для --changed (по умолчанию: HEAD)")
    s.add_argument(
        "--include-diffs",
        action="store_true",
        help="Включить unified diff для drifted connectors",
    )
    s.add_argument(
        "--max-lines",
        type=int,
        default=80,
        help="Максимум строк diff на один коннектор (когда --include-diffs)",
    )
    s.add_argument(
        "--top",
        type=int,
        default=15,
        help="Сколько top drift reasons вывести (по ключам конфига)",
    )
    add_output_format_args(s)
    s.add_argument(
        "--output-file",
        dest="output_file",
        help="Записать markdown в файл",
    )
    s.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Exit code != 0 если найден drift/missing",
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
    s.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Не спрашивать подтверждение для широкого multi-cluster drift",
    )
    s.set_defaults(func=handler)
    return s
