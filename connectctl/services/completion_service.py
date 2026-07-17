"""Backwards-compatible импорт.

Исторически команда `bkkt completion` использовала модуль `connectctl.services.completion_service`.
Чтобы не ломать импорты (и внешние интеграции), оставляем тонкий wrapper.
"""

from .completion.service import CompletionService

__all__ = ["CompletionService"]
