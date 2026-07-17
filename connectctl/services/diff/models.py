from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MissingItem:
    """Коннектор отсутствует в целевом кластере."""

    name: str
    cluster: str


@dataclass(frozen=True)
class DisabledItem:
    """Connector intentionally skipped because lifecycle is disabled."""

    name: str
    cluster: str
    manifest_rel: str
    reason: str
    ticket: str | None = None
    until: str | None = None


@dataclass(frozen=True)
class DriftItem:
    """Один drift-элемент в diff-отчёте."""

    name: str
    cluster: str
    diff: str
    trimmed: bool
    manifest_rel: str
    pruned_config_keys: tuple[str, ...] = ()
    diff_keys: tuple[str, ...] = ()
