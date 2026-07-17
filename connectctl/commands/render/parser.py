from __future__ import annotations

import argparse
from typing import Callable

from ...cli_helpers.output_args import add_output_format_args


def register_parser(
    subparsers: argparse._SubParsersAction,
    *,
    handler: Callable[[argparse.Namespace], int],
) -> argparse.ArgumentParser:
    s = subparsers.add_parser(
        "render", help="Отрендерить финальный manifest (после layered overrides)"
    )
    s.add_argument(
        "path",
        nargs="?",
        help=(
            "Путь к <env>.*.json манифесту (relative to repo root) "
            "или `trace` для bkkt render trace"
        ),
    )
    s.add_argument(
        "trace_path",
        nargs="?",
        help="Manifest path for `bkkt render trace <manifest>`",
    )
    add_output_format_args(s)
    s.add_argument(
        "--output-file",
        dest="output_file",
        help="Записать результат render в файл (формат берётся из --output)",
    )
    s.add_argument("--show-layers", action="store_true", help="Печатать список слоёв")
    s.add_argument(
        "--config-key",
        dest="config_key",
        default=None,
        help="Config key to explain when using `bkkt render trace`",
    )
    s.add_argument(
        "--include-contracts",
        action="store_true",
        help="Include typed variable contract metadata in `bkkt render trace` output",
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
        help="dbt-style vars JSON (object). Можно повторять; мерджится, побеждает последнее значение.",
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
        help=(
            "Имя профиля из bkkt/vars/profiles/*.yaml. Можно повторять; "
            "перебивается --vars-file и --vars."
        ),
    )

    # Layer minimization: allow rendering "raw" env manifests without repo-wide overrides.
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
        help="Ограничить набор override-файлов, которые учитываем при render/apply. Можно повторять. Пути relative to repo root.",
    )

    # Опционально: routing debug (используется только вместе с --explain-routing)
    s.add_argument(
        "--cluster",
        default=None,
        help="(опционально) Переопределить cluster group (routing + cluster render policy)",
    )
    s.add_argument(
        "--suppress-tag-conflicts",
        action="store_true",
        help="(опционально) Подавить конфликты тегов (для explain-routing)",
    )

    s.set_defaults(func=handler)
    return s
