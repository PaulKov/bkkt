"""Единые help-тексты для safety-опций CLI.

Зачем это нужно:
- один и тот же флаг встречается во многих командах
- текст должен быть консистентным (UX) и вести к документации

Важно: эти строки попадают и в автоматически сгенерированные docs/CLI_REFERENCE.*
"""

from __future__ import annotations


def strict_naming_disable_help(*, default_enabled: bool = True) -> str:
    """Help для флага отключения strict naming (обычно: --no-strict-naming)."""

    prefix = "Отключить" if default_enabled else "Выключить"
    return (
        f"{prefix} строгую валидацию нейминга (НЕ рекомендуется). "
        "Проверяет dot-style имена и базовые инварианты: env в начале, domain во 2-м сегменте, "
        "наличие 'source'/'sink' и system, последний сегмент — числовой индекс, "
        "а также (если настроено) правила connectctl.yaml:naming.rules. "
        "Подробнее: docs/NAMING.md (или `bkkt help naming`)."
    )


def strict_naming_enable_help() -> str:
    """Help для флага включения strict naming (обычно: --strict-naming)."""

    return (
        "Включить строгую валидацию нейминга (CI gate). "
        "Проверяет dot-style и (если настроено) connectctl.yaml:naming.rules. "
        "Подробнее: docs/NAMING.md (или `bkkt help naming`)."
    )


def policies_disable_help(*, default_enabled: bool = True) -> str:
    """Help для флага отключения policy-checks (обычно: --no-policies)."""

    prefix = "Отключить" if default_enabled else "Выключить"
    return (
        f"{prefix} policy‑проверки окружения (НЕ рекомендуется). "
        "Эти проверки ловят потенциально опасные ссылки на чужое окружение (dev/stage/prod) и другие ошибки. "
        "Подробнее: docs/POLICIES.md (или `bkkt help policies`)."
    )
