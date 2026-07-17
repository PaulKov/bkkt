from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Iterable

from ..logging_utils import get_logger
from .explicit_args import was_explicit


@dataclass(frozen=True)
class EffectiveValue:
    name: str
    value: str
    implicit: bool = False


def effective_value(
    args: object,
    dest: str,
    value: object,
    *,
    name: str | None = None,
) -> EffectiveValue:
    rendered = _render_value(value)
    return EffectiveValue(
        name=name or dest,
        value=rendered,
        implicit=not was_explicit(args, dest),
    )


def log_effective_values(
    logger: logging.Logger | None,
    *,
    command: str,
    values: Iterable[EffectiveValue],
) -> str:
    log = get_logger(logger)
    text = ", ".join(_render_effective_value(item) for item in values)
    log.info("Effective selection for %s: %s", command, text)
    return text


def confirm_broad_scope(
    args: object,
    *,
    prompt: str,
    logger: logging.Logger | None = None,
) -> bool:
    if bool(getattr(args, "yes", False)):
        return True
    if not is_interactive_terminal():
        return True
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    if answer in {"y", "yes"}:
        return True
    get_logger(logger).warning("Отменено.")
    return False


def is_interactive_terminal() -> bool:
    if os.environ.get("CI"):
        return False
    stdin = getattr(sys.stdin, "isatty", lambda: False)()
    stdout = getattr(sys.stdout, "isatty", lambda: False)()
    return bool(stdin and stdout)


def _render_effective_value(item: EffectiveValue) -> str:
    suffix = " (implicit)" if item.implicit else ""
    return f"{item.name}={item.value}{suffix}"


def _render_value(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, (list, tuple, set, frozenset)):
        if not value:
            return "-"
        return ",".join(str(item) for item in value)
    return str(value)


__all__ = [
    "EffectiveValue",
    "confirm_broad_scope",
    "effective_value",
    "is_interactive_terminal",
    "log_effective_values",
]
