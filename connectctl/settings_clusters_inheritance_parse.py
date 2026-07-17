from __future__ import annotations

import re
from typing import Optional, Sequence

from .exceptions import ConfigError


FROM_FUNC_NAME = "from_cluster_group_env"
FROM_FUNC_RE = re.compile(rf"^\s*{FROM_FUNC_NAME}\s*\((.*)\)\s*$")


def _split_func_args(inner: str) -> Sequence[str]:
    """Разделить аргументы inside from_cluster_group_env(...).

    Поддерживается:
      - from_cluster_group_env(acme-main, 'all')
      - from_cluster_group_env("acme-main", "connect.port")
      - from_cluster_group_env(acme-main)

    Кавычки (одинарные/двойные) необязательны для первого аргумента.
    Экранирование обратным слэшем поддерживается внутри кавычек.
    """
    args: list[str] = []
    buf: list[str] = []
    quote: Optional[str] = None
    esc = False

    for ch in inner:
        if esc:
            buf.append(ch)
            esc = False
            continue

        if quote:
            if ch == "\\":
                esc = True
                continue
            if ch == quote:
                quote = None
                continue
            buf.append(ch)
            continue

        # not in quote
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == ",":
            args.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)

    if quote:
        raise ConfigError(f"{FROM_FUNC_NAME}(): unclosed quote in: {inner!r}")

    tail = "".join(buf).strip()
    if tail:
        args.append(tail)
    return args


def parse_from_cluster_group_env_call(s: str) -> Optional[tuple[str, str]]:
    """Распарсить строку вида from_cluster_group_env(group, selector)."""
    m = FROM_FUNC_RE.match(str(s))
    if not m:
        return None
    inner = (m.group(1) or "").strip()
    if not inner:
        raise ConfigError(
            f"{FROM_FUNC_NAME}() requires at least 1 argument: group name"
        )

    args = list(_split_func_args(inner))
    group = (args[0] or "").strip()
    if not group:
        raise ConfigError(f"{FROM_FUNC_NAME}(): group name must not be empty")

    selector = (args[1] if len(args) > 1 else "all") or "all"
    selector = str(selector).strip() or "all"
    return group, selector
