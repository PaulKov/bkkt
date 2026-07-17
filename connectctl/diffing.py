from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple


_SENSITIVE_KEY_RE = re.compile(
    r"(?i)(password|secret|token|api[_-]?key|sasl\.jaas\.config|bearer|oauth|ssl\.key|ssl\.keystore|ssl\.truststore)"
)


def normalize_config(
    cfg: Mapping[str, Any], *, mask_secrets: bool = False
) -> Dict[str, str]:
    """Return a normalized config map suitable for comparisons/diffs.

    - Ensures values are strings
    - Drops the redundant 'name' key (connector name is the resource identifier)
    - Optionally masks sensitive values
    """

    out: Dict[str, str] = {}
    for k, v in cfg.items():
        if k == "name":
            continue
        sv = "" if v is None else str(v)
        if mask_secrets and _SENSITIVE_KEY_RE.search(k):
            sv = "***"
        out[str(k)] = sv
    return out


def configs_equal(desired: Mapping[str, Any], existing: Mapping[str, Any]) -> bool:
    return normalize_config(desired, mask_secrets=False) == normalize_config(
        existing, mask_secrets=False
    )


def config_unified_diff(
    *,
    connector_name: str,
    desired: Mapping[str, Any],
    existing: Mapping[str, Any],
    fromfile: str = "desired",
    tofile: str = "existing",
) -> str:
    """Create a unified diff between two connector configs (with secrets masked)."""

    a = normalize_config(desired, mask_secrets=True)
    b = normalize_config(existing, mask_secrets=True)

    a_json = json.dumps(a, indent=2, sort_keys=True, ensure_ascii=False).splitlines(
        keepends=True
    )
    b_json = json.dumps(b, indent=2, sort_keys=True, ensure_ascii=False).splitlines(
        keepends=True
    )

    diff = difflib.unified_diff(
        a_json,
        b_json,
        fromfile=f"{fromfile}:{connector_name}",
        tofile=f"{tofile}:{connector_name}",
    )
    return "".join(diff)


def summarize_diff(diff_text: str, *, max_lines: int = 200) -> Tuple[str, bool]:
    """Trim diff for MR comments; returns (text, trimmed)."""

    lines = diff_text.splitlines()
    if len(lines) <= max_lines:
        return diff_text, False
    trimmed = "\n".join(lines[:max_lines]) + "\n... (diff truncated)"
    return trimmed, True


@dataclass(frozen=True)
class ConfigKeyChanges:
    """Структурный diff между двумя config map.

    Дифф считается по нормализованным ключам/значениям (всё строками, без key 'name').
    Для определения факта изменения используются НЕ masked значения.

    Маскирование (*** для секретов) применяется только на этапе форматирования вывода.
    """

    added: Dict[str, str]
    removed: Dict[str, str]
    changed: Dict[str, Tuple[str, str]]  # key -> (old, new)

    def is_empty(self) -> bool:
        return not self.added and not self.removed and not self.changed


def config_key_changes(
    *,
    desired: Mapping[str, Any],
    existing: Mapping[str, Any],
) -> ConfigKeyChanges:
    """Вернуть added/removed/changed keys между desired и existing.

    Значения возвращаются как строки (без маскирования). Для безопасного вывода
    используйте format_config_key_changes(...), который применит маскирование.
    """

    a = normalize_config(desired, mask_secrets=False)
    b = normalize_config(existing, mask_secrets=False)

    a_keys = set(a.keys())
    b_keys = set(b.keys())

    added = {k: a[k] for k in sorted(a_keys - b_keys)}
    removed = {k: b[k] for k in sorted(b_keys - a_keys)}

    changed: Dict[str, Tuple[str, str]] = {}
    for k in sorted(a_keys & b_keys):
        if a[k] != b[k]:
            changed[k] = (b[k], a[k])

    return ConfigKeyChanges(added=added, removed=removed, changed=changed)


def _mask_value_for_key(key: str, value: str) -> str:
    if _SENSITIVE_KEY_RE.search(key):
        return "***"
    return value


def format_config_key_changes(
    changes: ConfigKeyChanges,
    *,
    max_keys_per_section: int = 50,
    indent: str = "  ",
) -> str:
    """Человекочитаемый diff: removed/added/changed.

    - removed/added: выводим список ключей
    - changed: выводим key: old -> new (значения маскируются для секретных ключей)
    """

    lines = []

    def _fmt_keys(title: str, keys: list[str]) -> None:
        if not keys:
            return
        shown = keys[:max_keys_per_section]
        tail = len(keys) - len(shown)
        if tail > 0:
            lines.append(
                f"{indent}{title} ({len(keys)}): " + ", ".join(shown) + f" … (+{tail})"
            )
        else:
            lines.append(f"{indent}{title} ({len(keys)}): " + ", ".join(shown))

    _fmt_keys("Удалённые ключи", list(changes.removed.keys()))
    _fmt_keys("Добавленные ключи", list(changes.added.keys()))

    if changes.changed:
        keys = list(changes.changed.keys())
        shown = keys[:max_keys_per_section]
        tail = len(keys) - len(shown)
        lines.append(f"{indent}Изменённые ключи ({len(keys)}):")
        for k in shown:
            old, new = changes.changed[k]
            old_m = _mask_value_for_key(k, old)
            new_m = _mask_value_for_key(k, new)
            lines.append(f"{indent}{indent}- {k}: {old_m!r} -> {new_m!r}")
        if tail > 0:
            lines.append(f"{indent}{indent}… и ещё {tail}")

    if not lines:
        return f"{indent}(нет изменений)"

    return "\n".join(lines)
