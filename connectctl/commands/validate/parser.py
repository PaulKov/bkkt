from __future__ import annotations

import argparse
from typing import Callable

from ...cli_helpers.safety_help import strict_naming_enable_help


def register_parser(
    subparsers: argparse._SubParsersAction,
    *,
    handler: Callable[[argparse.Namespace], int],
) -> argparse.ArgumentParser:
    """Register `connectctl validate` parser."""

    s = subparsers.add_parser(
        "validate", help="Валидация манифестов (render + базовые проверки)"
    )
    s.add_argument("--env", help="Валидировать только одно окружение (dev|stage|prod)")
    s.add_argument(
        "--changed",
        action="store_true",
        help="Валидировать только коннекторы, затронутые git diff",
    )
    s.add_argument(
        "--strict-naming",
        action="store_true",
        help=strict_naming_enable_help(),
    )
    s.add_argument(
        "--strict-schema",
        action="store_true",
        help="Строгая JSON Schema валидация: connectctl.yaml и manifest JSON (CI gate)",
    )
    s.add_argument(
        "--strict-schema-max",
        dest="strict_schema_max",
        type=int,
        default=20,
        help="Сколько schema ошибок показывать в логах (top-N). (default: 20)",
    )
    s.add_argument(
        "--strict-connector-dir",
        dest="strict_connector_dir",
        action="store_true",
        help=(
            "Считать repo-wide lint по шаблону connector_dir ошибкой (по умолчанию это warning). "
            "Проверка: connector_<domain>__<dataset>{__<optional_suffix>}"
        ),
    )
    s.add_argument(
        "--connector-dir-lint-scope",
        dest="connector_dir_lint_scope",
        choices=["all", "changed"],
        default="all",
        help=(
            "Область repo-wide lint для connector_dir. "
            "all=проверять весь репозиторий (по умолчанию). "
            "changed=проверять только каталоги, затронутые --changed (или явными путями в конце команды)."
        ),
    )
    s.add_argument(
        "--connector-dir-lint-max",
        dest="connector_dir_lint_max",
        type=int,
        default=20,
        help=(
            "Сколько нарушений connector_dir печатать в логах (top-N). "
            "Остальные будут свернуты как '… и ещё X…'. (default: 20)"
        ),
    )
    s.add_argument("--base", help="Base git sha (по умолчанию: auto)")
    s.add_argument("--head", help="Head git sha (по умолчанию: HEAD)")
    s.add_argument("paths", nargs="*", help="Явные manifest paths для валидации")
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
        help="Путь к JSON/YAML файлу vars (object). Можно повторять; мерджится. Перебивается --vars.",
    )
    s.add_argument(
        "--vars-profile",
        action="append",
        default=None,
        help="Имя профиля из bkkt/vars/profiles/*.yaml. Можно повторять.",
    )
    s.set_defaults(func=handler)
    return s
