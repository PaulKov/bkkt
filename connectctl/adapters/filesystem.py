"""Адаптеры FileSystem.

В проекте BKKT мы используем порт (Protocol) `FileSystem` для DI и тестируемости.

Реализации:
- LocalFileSystem — реальная файловая система (default)
- InMemoryFileSystem — простая in-memory FS для юнит-тестов

Этот модуль — facade для обратной совместимости импортов:

    from connectctl.adapters.filesystem import LocalFileSystem, InMemoryFileSystem
"""

from __future__ import annotations
from .filesystem_local import LocalFileSystem
from .filesystem_memory import InMemoryFileSystem

__all__ = ["LocalFileSystem", "InMemoryFileSystem"]
