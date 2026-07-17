"""Сканер репозитория коннекторов (facade).

Исторически в этом модуле было много логики: regex'ы, парсинг путей,
инференс mode/init/cdc, детект sink-variant и т.д.

В рамках рефакторинга код разнесён по SRP‑модулям:
  - scanner_regex.py
  - scanner_mode.py
  - scanner_variants.py
  - scanner_paths.py
  - scanner_repo.py

Этот файл оставлен как стабильная точка импорта:

    from connectctl.repo import ConnectorRepo

и

    from connectctl.repo.scanner import ConnectorRepo
"""

from __future__ import annotations

from .scanner_repo import ConnectorRepo

__all__ = ["ConnectorRepo"]
