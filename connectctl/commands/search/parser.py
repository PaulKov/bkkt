from __future__ import annotations

import argparse

from ...cli_helpers.concurrency_args import add_concurrency_args
from ...cli_helpers.output_args import add_output_format_args


def _append_csv_option(
    parser: argparse.ArgumentParser,
    *flags: str,
    dest: str,
    help_text: str,
) -> None:
    parser.add_argument(
        *flags,
        dest=dest,
        action="append",
        default=[],
        help=help_text,
    )


def _register_search_like_parser(
    subparsers: argparse._SubParsersAction,
    *,
    command_name: str,
    help_text: str,
    handler,
) -> argparse.ArgumentParser:
    s = subparsers.add_parser(command_name, help=help_text)
    s.add_argument(
        "--source",
        choices=["repo", "live", "both"],
        default="repo",
        help="Где искать коннекторы: repo=отрендеренные manifests, live=Kafka Connect, both=оба источника",
    )
    s.add_argument(
        "--env",
        default="all",
        help="Окружение для поиска: dev|stage|prod|all (по умолчанию: all)",
    )
    s.add_argument(
        "--cluster",
        default="all",
        help="Cluster group filter: <name>|all (по умолчанию: all)",
    )
    s.add_argument(
        "--view",
        choices=["short", "long"],
        default="long",
        help="Формат текстового представления: short|long",
    )
    s.add_argument(
        "--explain",
        choices=["long", "stats", "none"],
        default="long",
        help=(
            "Explainable search output: long=match paths and related occurrences, "
            "stats=compact config statistics by env/cluster, none=legacy match output only"
        ),
    )
    s.add_argument(
        "--limit", type=int, default=None, help="Ограничить число результатов"
    )
    s.add_argument(
        "--ignore-case",
        action="store_true",
        help="Игнорировать регистр для exact/prefix/suffix/regex matching",
    )
    s.add_argument(
        "--list-vars",
        action="store_true",
        help="Показать разрешенные ${...} variables для search filters и выйти",
    )
    s.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Не спрашивать подтверждение для широкого live поиска",
    )
    add_output_format_args(s)
    add_concurrency_args(s, default_jobs=8)

    _append_csv_option(
        s,
        "--name",
        dest="name",
        help_text="Точное совпадение имени коннектора (можно повторять, CSV тоже поддерживается)",
    )
    _append_csv_option(
        s,
        "--name-prefix",
        dest="name_prefix",
        help_text="Искать коннекторы по prefix имени",
    )
    _append_csv_option(
        s,
        "--name-suffix",
        dest="name_suffix",
        help_text="Искать коннекторы по suffix имени",
    )
    _append_csv_option(
        s,
        "--name-regexp",
        dest="name_regexp",
        help_text="Искать коннекторы по regex имени",
    )
    _append_csv_option(
        s,
        "--name-fuzzy",
        dest="name_fuzzy",
        help_text="Нечеткий поиск по имени коннектора (typo-tolerant)",
    )

    _append_csv_option(
        s,
        "--table",
        dest="table",
        help_text="Искать по таблицам (source/sink), можно повторять и передавать CSV",
    )
    _append_csv_option(
        s,
        "--table-prefix",
        dest="table_prefix",
        help_text="Искать по prefix таблиц",
    )
    _append_csv_option(
        s,
        "--table-suffix",
        dest="table_suffix",
        help_text="Искать по suffix таблиц",
    )
    _append_csv_option(
        s,
        "--table-regexp",
        dest="table_regexp",
        help_text="Искать по regex таблиц",
    )
    s.add_argument(
        "--table-match",
        choices=["any", "all"],
        default="any",
        help="Как матчить несколько значений таблиц: any|all",
    )

    _append_csv_option(
        s,
        "--topic",
        dest="topic",
        help_text="Искать по consumed/produced topics, можно повторять и передавать CSV",
    )
    _append_csv_option(
        s,
        "--topic-prefix",
        dest="topic_prefix",
        help_text="Искать по prefix topics",
    )
    _append_csv_option(
        s,
        "--topic-suffix",
        dest="topic_suffix",
        help_text="Искать по suffix topics",
    )
    _append_csv_option(
        s,
        "--topic-regexp",
        dest="topic_regexp",
        help_text="Искать по regex topics",
    )
    s.add_argument(
        "--topic-match",
        choices=["any", "all"],
        default="any",
        help="Как матчить несколько значений topics: any|all",
    )

    _append_csv_option(s, "--domain", dest="domain", help_text="Фильтр по domain")
    _append_csv_option(s, "--dataset", dest="dataset", help_text="Фильтр по dataset")
    s.add_argument(
        "--type",
        dest="connector_type",
        action="append",
        default=[],
        choices=["source", "sink"],
        help="Фильтр по типу коннектора (source|sink)",
    )
    _append_csv_option(s, "--system", dest="system", help_text="Фильтр по system")
    _append_csv_option(s, "--layer", dest="layer", help_text="Фильтр по layer")
    _append_csv_option(s, "--mode", dest="mode", help_text="Фильтр по mode")
    _append_csv_option(s, "--kind", dest="kind", help_text="Фильтр по kind")

    _append_csv_option(s, "--host", dest="host", help_text="Искать по db host")
    _append_csv_option(
        s,
        "--kafka-bootstrap",
        dest="kafka_bootstrap",
        help_text="Искать коннекторы по Kafka bootstrap config values",
    )
    _append_csv_option(
        s,
        "--schema-registry-url",
        "--schema-registry",
        dest="schema_registry_url",
        help_text="Искать коннекторы по Schema Registry config values",
    )
    _append_csv_option(
        s,
        "--database",
        dest="database",
        help_text="Искать по database / namespace",
    )
    _append_csv_option(s, "--schema", dest="schema", help_text="Искать по schema")
    _append_csv_option(
        s, "--server", dest="server", help_text="Искать по server-like identifiers"
    )

    _append_csv_option(
        s,
        "--has-config-key",
        dest="has_config_key",
        help_text="Искать где config key существует",
    )
    s.add_argument(
        "--config-eq",
        action="append",
        default=[],
        help="Искать по config exact match в формате KEY=VALUE",
    )
    s.add_argument(
        "--config-prefix",
        action="append",
        default=[],
        help="Искать по config prefix match в формате KEY=VALUE",
    )
    s.add_argument(
        "--config-suffix",
        action="append",
        default=[],
        help="Искать по config suffix match в формате KEY=VALUE",
    )
    s.add_argument(
        "--config-regexp",
        action="append",
        default=[],
        help="Искать по config regex match в формате KEY=REGEX",
    )

    s.add_argument(
        "--where",
        action="append",
        default=[],
        help=(
            "Boolean query: AND/OR/NOT, (), =, !=, ^=, $=, ~=, "
            'exists(field), missing(field), config("key")'
        ),
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
    s.set_defaults(func=handler, requires_config=False)
    return s


def register_parser(subparsers: argparse._SubParsersAction, *, handler):
    parser = _register_search_like_parser(
        subparsers,
        command_name="search",
        help_text="Гибкий поиск коннекторов по repo/live фактам и config-предикатам",
        handler=handler,
    )
    _register_search_like_parser(
        subparsers,
        command_name="find",
        help_text="(алиас) search",
        handler=handler,
    )
    return parser
