from __future__ import annotations

from enum import Enum
import json
import sys
from typing import Any

import yaml


class OutputFormat(str, Enum):
    """Формат вывода результата команды в stdout."""

    text = "text"
    json = "json"
    yaml = "yaml"

    # Backwards-compatible aliases.
    #
    # Внутри кода BKKT мы исторически используем `OutputFormat.text/json/yaml`.
    # При этом некоторые команды (или внешние плагины/скрипты) могут ожидать
    # enum-стиль в UPPER_CASE: TEXT/JSON/YAML.
    #
    # Чтобы избежать падений вида `AttributeError: OutputFormat has no attribute TEXT`,
    # поддерживаем оба стиля. Верхние имена являются алиасами тех же значений.
    TEXT = "text"
    JSON = "json"
    YAML = "yaml"


def resolve_output_format(
    args: object, *, default: OutputFormat = OutputFormat.text
) -> OutputFormat:
    """Определить итоговый формат вывода.

    Поддерживает backward-compatible alias `--json`.

    Правила:
    - если `args.output` задан (строка): используем его как формат (text/json/yaml)
    - иначе, если `args.json == True`: формат = json
    - иначе: default
    """

    out = getattr(args, "output", None)
    if isinstance(out, str) and out.strip():
        try:
            return OutputFormat(out.strip())
        except ValueError:
            # Обычно парсеры ограничивают choices, но на всякий случай.
            return default

    if bool(getattr(args, "json", False)):
        return OutputFormat.json
    return default


def is_machine_output(fmt: OutputFormat) -> bool:
    return fmt in (OutputFormat.json, OutputFormat.yaml)


def write_text(text: str) -> None:
    """Пишет текст в stdout.

    Принцип BKKT:
    - stdout: основной результат команды (Markdown/табличка/JSON и т.п.)
    - stderr: логи выполнения (BKKT LOG)

    Это позволяет безопасно пайпить stdout в другие утилиты.
    """

    sys.stdout.write(text)


def write_json(obj: Any, *, indent: int = 2, sort_keys: bool = True) -> None:
    """Пишет JSON в stdout и добавляет перевод строки."""

    sys.stdout.write(dumps_json(obj, indent=indent, sort_keys=sort_keys))


def write_yaml(obj: Any, *, sort_keys: bool = False) -> None:
    """Пишет YAML в stdout и добавляет перевод строки."""

    sys.stdout.write(dumps_yaml(obj, sort_keys=sort_keys))


def dumps_json(obj: Any, *, indent: int = 2, sort_keys: bool = True) -> str:
    """Сериализовать объект в JSON строку (с переводом строки)."""

    return (
        json.dumps(obj, indent=indent, sort_keys=sort_keys, ensure_ascii=False) + "\n"
    )


def dumps_yaml(obj: Any, *, sort_keys: bool = False) -> str:
    """Сериализовать объект в YAML строку (с переводом строки)."""

    return (
        yaml.safe_dump(
            obj,
            allow_unicode=True,
            sort_keys=sort_keys,
            default_flow_style=False,
        ).rstrip()
        + "\n"
    )


def dumps_payload(payload: Any, *, fmt: OutputFormat) -> str:
    """Сериализовать payload в строку согласно fmt (с переводом строки)."""

    if fmt == OutputFormat.json:
        return dumps_json(payload)
    if fmt == OutputFormat.yaml:
        return dumps_yaml(payload)
    raise ValueError(f"dumps_payload: unsupported format for payload: {fmt}")


def write_payload(payload: Any, *, fmt: OutputFormat) -> None:
    """Вывести payload (dict/list) в stdout в заданном формате."""

    sys.stdout.write(dumps_payload(payload, fmt=fmt))
