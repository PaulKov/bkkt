from __future__ import annotations

import argparse
from typing import Callable

from ...cli_helpers.concurrency_args import add_concurrency_args
from ...cli_helpers.audit_args import add_audit_args
from ...cli_helpers.failure_bundle_args import add_failure_bundle_dir_arg
from ...cli_helpers.safety_help import policies_disable_help, strict_naming_disable_help
from ...cli_helpers.timeout_args import add_wait_timeout_seconds_args


def register_parser(
    subparsers: argparse._SubParsersAction,
    *,
    handler: Callable[[argparse.Namespace], int],
) -> argparse.ArgumentParser:
    """Зарегистрировать парсер для `bkkt apply`.

    Реальная логика apply находится в сервисе (слой services/*).
    Этот модуль — тонкий адаптер CLI, чтобы файлы команд не разрастались.
    """

    s = subparsers.add_parser(
        "apply",
        help="Применить (deploy/update) коннекторы в Kafka Connect через REST API",
    )
    s.add_argument("--env", required=True, help="Окружение (dev|stage|prod)")
    add_audit_args(s)
    s.add_argument(
        "--cluster",
        default=None,
        help="Имя группы кластеров (cluster group). По умолчанию: default_cluster из connectctl.yaml",
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
        help="Применить только коннекторы, затронутые git diff",
    )
    s.add_argument("--base", help="Base git sha (по умолчанию: auto)")
    s.add_argument("--head", help="Head git sha (по умолчанию: auto)")
    s.add_argument(
        "--dry-run",
        action="store_true",
        help="Режим без изменений: не вызывать Kafka Connect API",
    )
    s.add_argument(
        "--runtime-unsafe-rest",
        action="store_true",
        help=(
            "Break-glass: allow raw Kafka Connect REST mutations for operator-managed "
            "runtimes (Strimzi/CFK). Prefer CRD/GitOps mutation instead."
        ),
    )
    s.add_argument(
        "--schema-preflight",
        dest="schema_preflight",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Run Schema Registry risk preflight before live upsert. "
            "--no-schema-preflight is break-glass and requires --schema-preflight-reason."
        ),
    )
    s.add_argument(
        "--schema-preflight-reason",
        default=None,
        help="Required audit reason when using --no-schema-preflight.",
    )
    s.add_argument(
        "--vars-preflight",
        dest="vars_preflight",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Run deploy-context vars/provider/secret preflight before apply. "
            "--no-vars-preflight is break-glass and requires --vars-preflight-reason."
        ),
    )
    s.add_argument(
        "--vars-preflight-reason",
        default=None,
        help="Required audit reason when using --no-vars-preflight.",
    )
    s.add_argument(
        "--vars-preflight-provider-contract",
        action="append",
        default=None,
        help=(
            "Provider contract YAML file or directory. Can be repeated. "
            "Default: bkkt/var_providers/contracts/**/*.yaml."
        ),
    )
    s.add_argument(
        "--vars-preflight-secret-index",
        default=None,
        help=(
            "Optional YAML index of allowed external secret refs for exact "
            "preflight without fetching secret values."
        ),
    )
    add_failure_bundle_dir_arg(s, command="apply")

    # Parallelism / safety
    add_concurrency_args(s)
    s.add_argument(
        "--connect-validate",
        dest="connect_validate",
        action="store_true",
        help="Проверять конфиг через Kafka Connect validate endpoint перед upsert (по умолчанию: включено)",
    )
    s.add_argument(
        "--no-connect-validate",
        dest="connect_validate",
        action="store_false",
        help="Пропустить валидацию конфига через Kafka Connect (НЕ рекомендуется)",
    )
    s.add_argument(
        "--rollback-on-fail",
        dest="rollback_on_fail",
        action="store_true",
        help="Откатывать на предыдущий конфиг при ошибке deploy (по умолчанию: включено на stage/prod)",
    )
    s.add_argument(
        "--no-rollback-on-fail",
        dest="rollback_on_fail",
        action="store_false",
        help="Выключить откат при ошибке",
    )
    s.add_argument(
        "--health-gates",
        action="store_true",
        help=(
            "Operator UX alias: enforce validate + wait healthy + smoke checks "
            "(safe no-op if those defaults are already enabled)"
        ),
    )
    s.add_argument(
        "--post-smoke",
        dest="smoke",
        action="store_true",
        help="Run post-deploy smoke checks (alias for default smoke behavior)",
    )
    s.add_argument(
        "--wait-seconds",
        type=float,
        default=10,
        help="Пауза после deploy перед опросом статуса (сек.)",
    )
    add_wait_timeout_seconds_args(
        s,
        default=300.0,
        timeout_help="Общий таймаут ожидания статуса (сек.)",
    )
    s.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=5,
        help="Интервал опроса статуса (сек.)",
    )
    s.add_argument(
        "paths",
        nargs="*",
        help="Явные пути к манифестам для apply (если не указан --changed)",
    )
    s.add_argument(
        "--expand-templates",
        action="store_true",
        default=False,
        help=(
            "Включить template-aware apply: разворачивать template‑манифесты с ${...} в имени файла, "
            "используя instances (prod.instances.json/instances.json) или vars.index/vars.instances. "
            "Также пытается резолвить отсутствующие запрошенные instance‑файлы: находит подходящий template и "
            "извлекает vars из имени файла."
        ),
    )
    s.add_argument(
        "--show-vars",
        dest="show_vars",
        action="store_true",
        default=True,
        help="Печатать provenance vars для каждого применяемого коннектора (по умолчанию: включено)",
    )
    s.add_argument(
        "--no-show-vars",
        dest="show_vars",
        action="store_false",
        help="Не показывать provenance vars",
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
        help=(
            "Путь к JSON/YAML файлу с vars (object). Можно повторять; мерджится. "
            "Значения из --vars имеют приоритет."
        ),
    )
    s.add_argument(
        "--vars-profile",
        action="append",
        default=None,
        help="Имя профиля из bkkt/vars/profiles/*.yaml. Можно повторять.",
    )

    # Layer minimization: allow applying "raw" env manifests without repo-wide overrides.
    s.add_argument(
        "--no-reuse-overrides",
        dest="reuse_overrides",
        action="store_false",
        default=True,
        help="Не применять repo-wide overrides (использовать только base.*.json + env manifest). Полезно для raw-конфигов.",
    )
    s.add_argument(
        "--reuse-from",
        dest="reuse_from",
        action="append",
        default=None,
        help="Ограничить набор override-файлов, которые учитываем при apply/render. Можно повторять. Пути relative to repo root.",
    )

    # Printing the final config (like render)
    s.add_argument(
        "--print-config",
        dest="print_config",
        action="store_true",
        default=True,
        help="Печатать итоговый конфиг каждого коннектора перед apply (по умолчанию: включено)",
    )
    s.add_argument(
        "--no-print-config",
        dest="print_config",
        action="store_false",
        help="Не печатать итоговый конфиг коннекторов",
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
        help="Выключить skip-if-unchanged (drift-skip) и всегда делать upsert",
    )
    s.add_argument(
        "--force",
        action="store_true",
        help="Форсировать upsert даже если конфиг не изменился",
    )

    # Optional destructive deploy options (disabled by default)
    s.add_argument(
        "--drop-if-exists",
        dest="drop_if_exists",
        action="store_true",
        default=False,
        help="Удалить коннектор перед apply, если он уже существует (ОПАСНО)",
    )
    s.add_argument(
        "--drop-if-failed",
        dest="drop_if_failed",
        action="store_true",
        default=False,
        help="Если deploy упал и коннектор оказался в FAILED — удалить его (по умолчанию: выключено)",
    )

    # Artifact-based deploy input
    s.add_argument(
        "--from-rendered",
        dest="from_rendered",
        default=None,
        help="Каталог с заранее отрендеренными JSON артефактами коннекторов",
    )
    s.add_argument(
        "--artifact-strict",
        action="store_true",
        default=False,
        help="При использовании --from-rendered: упасть, если отсутствует хотя бы один артефакт (CI-safe)",
    )

    # Iceberg Glue catalog bootstrap (enabled by default)
    s.add_argument(
        "--no-auto-catalog",
        dest="auto_catalog",
        action="store_false",
        default=True,
        help="Выключить авто‑создание баз данных AWS Glue для Iceberg sinks",
    )

    # Post-deploy smoke checks (enabled by default, non-fatal)
    s.add_argument(
        "--no-smoke",
        dest="smoke",
        action="store_false",
        default=True,
        help="Выключить smoke checks Kafka (наличие топиков / lag для sink)",
    )
    s.add_argument(
        "--smoke-strict",
        dest="smoke_strict",
        action="store_true",
        default=False,
        help="Завершать команду ошибкой, если smoke checks нашли проблемы",
    )

    s.set_defaults(connect_validate=True, rollback_on_fail=None)
    s.set_defaults(func=handler)
    return s
