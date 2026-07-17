from __future__ import annotations

import argparse
from typing import Callable


def register_parser(
    subparsers: argparse._SubParsersAction,
    *,
    handler: Callable[[argparse.Namespace], int],
) -> argparse.ArgumentParser:
    """Register `connectctl init` parser.

    Parser lives in a separate module to keep command adapter modules small.
    """

    p_init = subparsers.add_parser(
        "init", help="Сгенерировать структуру коннектора и манифест(ы)"
    )

    p_init.epilog = (
        "Подробнее про init templates, modes/kinds и порядок overrides: docs/INIT.md\n"
        "\n"
        "Шаблоны: built-in → __init_templates/ (или BKKT_INIT_TEMPLATES_ROOT).\n"
        "Overrides: BKKT_INIT_TPL/BKKT_INIT_TPL_FILE → --tpl-* → --tpl-stdin (последние побеждают).\n"
        "Scoped overrides: <scope>:..., где scope — glob относительно connector_dir "
        "(например: modes/init/*, types/events/*)."
    )

    p_init.add_argument(
        "--domain", required=True, help="Домен (папка верхнего уровня), напр. merchants"
    )
    p_init.add_argument(
        "--type",
        dest="connector_type",
        choices=["source", "sink"],
        required=True,
        help="Тип коннектора",
    )
    p_init.add_argument(
        "--system",
        required=True,
        help="Система (папка), напр. postgres/mysql/iceberg/clickhouse/mariadb",
    )
    p_init.add_argument(
        "--connector-dir",
        required=False,
        default=None,
        help=(
            "Имя директории коннектора. Необязательный параметр. "
            "По умолчанию: connector_<domain>__<dataset>. "
            "Должно соответствовать шаблону: connector_<domain>__<dataset>{__<optional_suffix>}"
        ),
    )
    p_init.add_argument(
        "--env",
        action="append",
        choices=["dev", "stage", "prod"],
        required=True,
        help="Окружение(я); можно указывать несколько раз",
    )
    p_init.add_argument(
        "--modes",
        action="append",
        default=None,
        help=(
            "Только для source. Список (CSV или повторяемый) режимов (modes) для генерации. "
            "Встроенные: cdc, init (алиасы: stream->cdc, initial->init). "
            "Также можно указывать свои modes (например backfill/replay) — init создаст modes/<mode>/* и вставит токен в имя (.backfill.). "
            "Пример: --modes init,cdc"
        ),
    )
    p_init.add_argument(
        "--init-only",
        dest="init_only",
        action="store_true",
        default=False,
        help=(
            "Только для source. Удобный флаг: создаёт <connector_dir>/modes/init/all.json с "
            "vars.debezium_snapshot_mode_init=initial_only (чтобы init был init-only из коробки). "
            "Если --modes указан, но init/initial отсутствуют — init будет добавлен автоматически."
        ),
    )
    p_init.add_argument(
        "--kinds",
        action="append",
        default=None,
        help=(
            "Только для sink. Список (CSV или повторяемый) sink kinds (variants) для генерации. "
            "Для CDC sink kind попадает в имя как '.cdc.<kind>.' и включает overlays 'types/<kind>/*'. "
            "Если --kinds не задан, генерируется простой sink без '.cdc' (kind будет выведен из --layer: raw/ods, либо 'default'). "
            "Пример: --kinds events,flatten"
        ),
    )
    p_init.add_argument(
        "--dataset",
        default="CHANGE_ME",
        help="Dataset (используется в шаблонах и connector_dir)",
    )
    p_init.add_argument(
        "--layer",
        default="raw",
        help=(
            "Только для sink. Логический слой (обычно raw или ods): попадает в имя после `.sink.` и в vars.layer. "
            "Для non-CDC sink (без `.cdc`) также влияет на kind (types/raw vs types/ods)."
        ),
    )
    p_init.add_argument(
        "--index", type=int, default=0, help="Index для дефолтного шаблона имени"
    )
    p_init.add_argument(
        "--name", default=None, help="Явное имя коннектора (или format string)"
    )
    p_init.add_argument(
        "--name-template",
        default=None,
        help=(
            "Python format string для имени. Доступные переменные: env, domain, dataset, type, system, layer, index, "
            "connector_dir, mode, kind. Пример: '{env}.{domain}.{dataset}.source.{system}.{mode}.dbt.{index}'"
        ),
    )
    p_init.add_argument(
        "--create-all",
        dest="create_all",
        action="store_true",
        default=True,
        help="Создать all.json в директории коннектора",
    )
    p_init.add_argument(
        "--no-create-all",
        dest="create_all",
        action="store_false",
        help="Не создавать all.json",
    )
    p_init.add_argument(
        "--force", action="store_true", help="Перезаписывать существующие файлы"
    )
    p_init.add_argument(
        "--dry-run", action="store_true", help="Показать действия без записи файлов"
    )
    # Переопределения значений для init-templates (по аналогии с connect patch/update):
    #   - JSON: --tpl-json / --tpl-json-file
    #   - key=value: --tpl-set / --tpl-set-file
    #   - stdin: --tpl-stdin
    # Также поддерживаются env vars:
    #   - BKKT_INIT_TPL (JSON или key=value)
    #   - BKKT_INIT_TPL_FILE (путь к файлу с JSON или key=value)
    p_init.add_argument(
        "--tpl-json",
        dest="tpl_json",
        action="append",
        default=None,
        help=(
            "JSON overrides для init-templates (vars/config). Можно несколько раз. Поддерживается scoped формат: <scope>:<json>. "
            "Scope — glob относительно connector_dir (например: 'modes/init/*', 'types/events/*'). "
            "Порядок приоритетов (low->high): built-in < __init_templates/ (или BKKT_INIT_TEMPLATES_ROOT) < BKKT_INIT_TPL/BKKT_INIT_TPL_FILE < --tpl-* < --tpl-stdin. "
            "Поздние значения имеют более высокий приоритет. "
            "Если JSON не содержит ключей vars/config — он трактуется как набор config-ключей."
        ),
    )
    p_init.add_argument(
        "--tpl-json-file",
        dest="tpl_json_file",
        action="append",
        default=None,
        help=(
            "Файл с JSON overrides для init-templates. Можно несколько раз. Поддерживается scoped формат: <scope>:<path>."
        ),
    )
    p_init.add_argument(
        "--tpl-json-scoped",
        dest="tpl_json_scoped",
        action="append",
        default=None,
        help=(
            "[LEGACY] Scoped JSON overrides для init-templates. Формат: <scope>:<json>. Рекомендуется использовать --tpl-json '<scope>:<json>' без отдельного флага. "
            "Scope — glob относительно connector_dir (например: 'modes/init/*' или 'types/events/*'). "
            "Можно несколько раз; поздние значения имеют более высокий приоритет."
        ),
    )
    p_init.add_argument(
        "--tpl-json-file-scoped",
        dest="tpl_json_file_scoped",
        action="append",
        default=None,
        help=(
            "[LEGACY] Файл со scoped JSON overrides. Формат: <scope>:<path>. Рекомендуется использовать --tpl-json-file '<scope>:<path>' без отдельного флага. "
            "Пример: 'modes/init/*:overrides.json'. Можно несколько раз."
        ),
    )
    p_init.add_argument(
        "--tpl-set",
        dest="tpl_set",
        action="append",
        default=None,
        help=(
            "key=value overrides для init-templates (CSV). Можно несколько раз. Поддерживается scoped формат: <scope>:k=v[,k=v]. "
            "Scope — glob относительно connector_dir (например: 'modes/init/*', 'types/events/*'). "
            "Поддерживается префикс vars.<path> и config.<key>. "
            "Если префикса нет — ключ пытается матчиться в vars, иначе считается config-ключом."
        ),
    )
    p_init.add_argument(
        "--tpl-set-file",
        dest="tpl_set_file",
        action="append",
        default=None,
        help=(
            "Файл с key=value overrides для init-templates (по строкам или CSV). Можно несколько раз. Поддерживается scoped формат: <scope>:<path>."
        ),
    )
    p_init.add_argument(
        "--tpl-set-scoped",
        dest="tpl_set_scoped",
        action="append",
        default=None,
        help=(
            "[LEGACY] Scoped key=value overrides для init-templates. Формат: <scope>:k=v[,k=v]. Рекомендуется использовать --tpl-set '<scope>:k=v' без отдельного флага. "
            "Пример: 'types/events/*:vars.layer=events,vars.index=1'. Можно несколько раз."
        ),
    )
    p_init.add_argument(
        "--tpl-set-file-scoped",
        dest="tpl_set_file_scoped",
        action="append",
        default=None,
        help=(
            "[LEGACY] Файл со scoped key=value overrides. Формат: <scope>:<path>. Рекомендуется использовать --tpl-set-file '<scope>:<path>' без отдельного флага. "
            "Пример: 'modes/init/*:overrides.kv'. Можно несколько раз."
        ),
    )
    p_init.add_argument(
        "--tpl-stdin",
        dest="tpl_stdin",
        action="store_true",
        default=False,
        help="Также прочитать overrides из stdin (JSON или key=value). Применяется последним.",
    )
    p_init.set_defaults(func=handler)
    return p_init
