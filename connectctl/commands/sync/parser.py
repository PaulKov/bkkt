from __future__ import annotations

import argparse
from typing import Callable

from ...cli_helpers.safety_help import policies_disable_help, strict_naming_disable_help


def register_parser(
    subparsers: argparse._SubParsersAction,
    *,
    handler: Callable[[argparse.Namespace], int],
) -> argparse.ArgumentParser:
    """Register `connectctl sync` parser."""

    s = subparsers.add_parser(
        "sync",
        help="Синхронизировать окружение: применить все манифесты из репозитория и (опционально) prune лишние",
    )
    s.add_argument("--env", required=True, help="Целевое окружение (dev|stage|prod)")
    s.add_argument(
        "--cluster",
        default=None,
        help=(
            "Имя группы кластеров (cluster group). "
            "Если задано — принудительно использовать этот кластер для всех коннекторов (override). "
            "Если не задано — sync работает в multi-cluster режиме и группирует коннекторы по routing "
            "(connectctl.cluster/tags/default_cluster), синхронизируя каждый кластер отдельно. "
            "Если вы хотите синхронизировать только один кластер, НЕ перекидывая все коннекторы override-ом, "
            "используйте --clusters (filter-by-cluster)."
        ),
    )
    s.add_argument(
        "--clusters",
        nargs="?",
        const="all",
        default=None,
        help=(
            "Фильтр sync по набору cluster groups (без override). "
            "Роутинг сохраняется: синхронизируются только 'естественные' коннекторы выбранных кластеров. "
            "Укажите список через запятую (например: main,source). "
            "Если указать без значения, включаются ВСЕ cluster groups из connectctl.yaml. "
            "Нельзя использовать вместе с --cluster (override)."
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
        "--prune",
        action="store_true",
        help="Удалить коннекторы, которые есть в Connect, но отсутствуют в repo",
    )
    s.add_argument(
        "--allow-regex",
        action="append",
        dest="allow_regex",
        default=[],
        help="Allow-list regex для имён коннекторов, которые можно prune (можно повторять)",
    )
    s.add_argument(
        "--deny-regex",
        action="append",
        dest="deny_regex",
        default=[],
        help="Deny-list regex для имён коннекторов, которые нельзя prune (можно повторять)",
    )
    s.add_argument(
        "--allow-name",
        action="append",
        dest="allow_name",
        default=[],
        help="Явный allow-list имён коннекторов для prune (можно повторять)",
    )
    s.add_argument(
        "--deny-name",
        action="append",
        dest="deny_name",
        default=[],
        help="Явный deny-list имён коннекторов для prune (можно повторять)",
    )
    s.add_argument(
        "--keep-regex",
        action="append",
        dest="keep_regex",
        default=[],
        help="(Deprecated) alias of --deny-regex. Regex имён коннекторов, которые надо сохранить при prune",
    )
    s.add_argument(
        "--dry-run",
        action="store_true",
        help="Ничего не применять в Kafka Connect (только показать план)",
    )
    s.add_argument(
        "--connect-validate",
        dest="connect_validate",
        action="store_true",
        help="Валидировать конфиг через plugin validate endpoint перед upsert (по умолчанию: включено)",
    )
    s.add_argument(
        "--no-connect-validate",
        dest="connect_validate",
        action="store_false",
        help="Отключить validate через Kafka Connect (НЕ рекомендуется)",
    )
    s.add_argument(
        "--rollback-on-fail",
        dest="rollback_on_fail",
        action="store_true",
        help="Rollback к предыдущей конфигурации при ошибке apply (по умолчанию: включено на stage/prod)",
    )
    s.add_argument(
        "--no-rollback-on-fail",
        dest="rollback_on_fail",
        action="store_false",
        help="Отключить rollback при ошибке",
    )
    s.add_argument(
        "--wait-seconds",
        type=float,
        default=10,
        help="Пауза после apply перед началом polling",
    )
    s.add_argument(
        "--timeout-seconds",
        type=float,
        default=300,
        help="Общий timeout ожидания статуса",
    )
    s.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=5,
        help="Интервал polling статуса",
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
        help="Путь к JSON/YAML файлу vars (object). Можно повторять; мерджится. Перебивается --vars.",
    )
    s.add_argument(
        "--vars-profile",
        action="append",
        default=None,
        help="Имя профиля из bkkt/vars/profiles/*.yaml. Можно повторять.",
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

    # Drift-skip (enabled by default)
    s.add_argument(
        "--no-skip-if-unchanged",
        dest="skip_if_unchanged",
        action="store_false",
        default=True,
        help="Отключить drift-skip и всегда делать upsert",
    )
    s.add_argument(
        "--force",
        action="store_true",
        help="Force upsert даже если конфиг не изменился",
    )
    s.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Не спрашивать подтверждение для широкого multi-cluster sync",
    )

    # Optional destructive deploy options (disabled by default)
    s.add_argument(
        "--drop-if-exists",
        dest="drop_if_exists",
        action="store_true",
        default=False,
        help="Удалять коннектор перед apply, если он уже существует (ОПАСНО)",
    )
    s.add_argument(
        "--drop-if-failed",
        dest="drop_if_failed",
        action="store_true",
        default=False,
        help="Если деплой упал и коннектор остался FAILED — удалить его (по умолчанию: выключено)",
    )

    # Iceberg Glue catalog bootstrap (enabled by default)
    s.add_argument(
        "--no-auto-catalog",
        dest="auto_catalog",
        action="store_false",
        default=True,
        help="Отключить авто-создание AWS Glue databases для Iceberg sinks",
    )

    # Post-deploy smoke checks (enabled by default, non-fatal)
    s.add_argument(
        "--no-smoke",
        dest="smoke",
        action="store_false",
        default=True,
        help="Отключить Kafka smoke checks (topics existence / sink lag)",
    )
    s.add_argument(
        "--smoke-strict",
        dest="smoke_strict",
        action="store_true",
        default=False,
        help="Падать с ошибкой, если smoke checks нашли проблемы",
    )

    s.set_defaults(connect_validate=True, rollback_on_fail=None)
    s.set_defaults(func=handler)
    return s
