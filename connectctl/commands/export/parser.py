from __future__ import annotations

import argparse

from ...cli_helpers.concurrency_args import add_concurrency_args


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    s = subparsers.add_parser(
        "export",
        help="Экспортировать существующие конфиги коннекторов из Kafka Connect в репозиторий (bootstrap GitOps)",
    )

    s.add_argument(
        "--env",
        required=True,
        help="Окружение/кластер, из которого экспортируем (dev|stage|prod)",
    )
    s.add_argument(
        "--cluster",
        default=None,
        help="Имя cluster group, из которого экспортируем (по умолчанию: default_cluster из connectctl.yaml)",
    )

    # Selection
    s.add_argument(
        "--all", action="store_true", help="Экспортировать все коннекторы из кластера"
    )
    s.add_argument(
        "--type",
        choices=["source", "sink"],
        help="Фильтр по типу коннектора (в основном вместе с --all)",
    )
    s.add_argument(
        "--domain",
        help="Домен (переопределение размещения для явных имен; фильтр для --all)",
    )
    s.add_argument(
        "--system",
        help="Система (переопределение размещения для явных имен; фильтр для --all)",
    )
    s.add_argument(
        "--connector-dir",
        dest="connector_dir",
        help="connector_dir (переопределение размещения для явных имен)",
    )

    # Collisions
    s.add_argument(
        "--auto-index-suffix-on-collision",
        dest="auto_index_suffix_on_collision",
        action="store_true",
        default=None,
        help=(
            "Если sink export конфликтует с существующим путём в repo (одно и то же размещение), "
            "автоматически дописать к connector_dir суффикс __<index> (по умолчанию: включено)"
        ),
    )
    s.add_argument(
        "--no-auto-index-suffix-on-collision",
        dest="auto_index_suffix_on_collision",
        action="store_false",
        help="Выключить автоматическое суффиксирование __<index> при коллизиях sink export",
    )

    s.add_argument(
        "--regexp",
        action="append",
        default=[],
        help="Экспортировать только коннекторы, где regexp матчится по имени или JSON конфигу (можно повторять)",
    )

    # Execution
    s.add_argument(
        "--dry-run",
        action="store_true",
        help="Режим без изменений: не писать файлы, только показать действия",
    )
    s.add_argument(
        "--force", action="store_true", help="Перезаписать существующие файлы"
    )

    # Parallelism / safety
    add_concurrency_args(s)

    # Reuse-overrides mode
    s.add_argument(
        "--reuse-overrides",
        dest="reuse_overrides",
        action="store_true",
        help="Пытаться минимизировать экспорт, переиспользуя repo overrides (по умолчанию: включено)",
    )
    s.add_argument(
        "--no-reuse-overrides",
        dest="reuse_overrides",
        action="store_false",
        help="Не переиспользовать overrides; записать сырой конфиг в env manifest (точная копия)",
    )
    s.add_argument(
        "--save-diffs",
        action="store_true",
        default=False,
        help=(
            "В режиме reuse_overrides (режим по умолчанию) сохранять значения из кластера даже если в repo есть override "
            "(дописать их в экспортированные манифесты) и записать diffs override-vs-remote в connector_dir/export/. "
            "По умолчанию: false (предпочитать repo overrides и опускать перекрытые ключи)."
        ),
    )
    s.add_argument(
        "--reuse-from",
        dest="reuse_from",
        action="append",
        default=[],
        help="Ограничить reuse overrides: использовать только эти override файлы как baseline (можно повторять)",
    )

    # Generic variants scaffolding (same UX as `bkkt init`)
    s.add_argument(
        "--modes",
        action="append",
        default=[],
        help=(
            "Для source export: дополнительно сгенерировать эти modes (через запятую, можно повторять). "
            "Встроенные: cdc, init (алиасы: stream->cdc, initial->init). "
            "Можно указывать свои modes (например backfill) — будут созданы modes/<mode>/* и name variants. "
            "Пример: --modes init,cdc"
        ),
    )
    s.add_argument(
        "--init-only",
        dest="init_only",
        action="store_true",
        default=False,
        help=(
            "Для source export: создать modes/init/all.json с debezium_snapshot_mode_init=initial_only. "
            "Также автоматически добавляет 'init' в --modes, если забыли."
        ),
    )
    s.add_argument(
        "--kinds",
        action="append",
        default=[],
        help=(
            "Для sink export: дополнительно сгенерировать эти kinds (через запятую, можно повторять). "
            "Kind попадает в имя как '.cdc.<kind>.' и включает overlays 'types/<kind>/*'. "
            "Для iceberg часто используются: events, flatten, raw, ods, default (но список не ограничен). "
            "Пример: --kinds events,flatten"
        ),
    )

    # Name override (remote name -> repo/manifest name)
    s.add_argument(
        "--as-name",
        dest="as_names",
        action="append",
        default=[],
        help=(
            "Переопределить имя коннектора в репозитории при export (удобно для миграции/нормализации). "
            "Поддерживаемые форматы (можно повторять): "
            "1) --as-name <new_name> (если экспортируется ровно 1 коннектор); "
            "2) --as-name <remote>=<new> (явное сопоставление); "
            "3) для N коннекторов: N раз --as-name <new_name> (по порядку)."
        ),
    )

    # Iceberg sink scaffolding
    s.add_argument(
        "--iceberg-generate-kinds",
        dest="iceberg_generate_kinds",
        action="append",
        default=[],
        help=(
            "Для Iceberg sinks: дополнительно сгенерировать manifests/overrides для этих kinds "
            "(через запятую, можно повторять). Пример: --iceberg-generate-kinds events,flatten"
        ),
    )
    s.add_argument(
        "--iceberg-table-id-columns",
        dest="iceberg_table_id_columns",
        action="append",
        default=[],
        help=(
            "Для Iceberg flatten scaffolding: задать id-columns mapping на таблицу в виде <table>=<col1,col2,...>. "
            "Можно повторять."
        ),
    )
    s.add_argument(
        "--iceberg-generate-overrides",
        dest="iceberg_generate_overrides",
        action="store_true",
        help=(
            "При использовании --iceberg-generate-kinds: также генерировать overrides types/<kind>/all.json "
            "(по умолчанию: включено)"
        ),
    )
    s.add_argument(
        "--no-iceberg-generate-overrides",
        dest="iceberg_generate_overrides",
        action="store_false",
        help="Выключить генерацию overrides types/<kind>/all.json (только manifests)",
    )
    s.add_argument(
        "--iceberg-generate-manifests",
        dest="iceberg_generate_manifests",
        action="store_true",
        help=(
            "При использовании --iceberg-generate-kinds: также генерировать env manifests для запрошенных kinds "
            "(по умолчанию: включено)"
        ),
    )
    s.add_argument(
        "--no-iceberg-generate-manifests",
        dest="iceberg_generate_manifests",
        action="store_false",
        help="Выключить генерацию env manifests (только overrides)",
    )

    # Connector names
    s.add_argument(
        "names", nargs="*", help="Имена коннекторов для экспорта (игнорируется с --all)"
    )

    # Runtime vars (for templated config in export)
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
            "Перебивается --vars."
        ),
    )
    s.add_argument(
        "--vars-profile",
        action="append",
        default=None,
        help="Имя профиля из bkkt/vars/profiles/*.yaml. Можно повторять.",
    )

    # Defaults
    s.set_defaults(reuse_overrides=True)
    s.set_defaults(iceberg_generate_overrides=True, iceberg_generate_manifests=True)

    return s
