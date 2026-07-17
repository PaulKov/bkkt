"""Конфигурируемые проверки коннекторов (config tests).

Исторически весь код был в одном модуле. В рамках рефакторинга мы разнесли
реализацию на несколько небольших модулей, но сохранили обратную совместимость:

- `from connectctl.validation import ConfigTestRunner`
- `from connectctl.validation import ConfigTestIssue`

Продолжайте импортировать из `connectctl.validation` — публичный API не изменился.
"""

from __future__ import annotations

from .config_tests_common import ConfigTestIssue
from .config_tests_runner import ConfigTestRunner

__all__ = ["ConfigTestRunner", "ConfigTestIssue"]
