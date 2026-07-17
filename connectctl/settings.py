"""Настройки BKKT (connectctl.yaml).

Этот модуль — фасад для обратной совместимости.

Раньше вся логика загрузки/парсинга находилась в `connectctl/settings.py`.
В ходе рефакторинга она вынесена в отдельные модули, но публичный API сохранён.
"""

from __future__ import annotations

# Публичные модели
from .settings_models import Settings, TagSettings

# Публичный helper
from .settings_loader import load_settings

# Backwards-compat re-exports
from .models import ConnectClusterConfig, Environment, KafkaConfig, RepoConfig

__all__ = [
    "Settings",
    "TagSettings",
    "load_settings",
    "Environment",
    "ConnectClusterConfig",
    "KafkaConfig",
    "RepoConfig",
]
