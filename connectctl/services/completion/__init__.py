"""Подсистема `completion`.

Содержит генерацию и установку argcomplete completion для разных shell.
"""

from .service import CompletionService

__all__ = ["CompletionService"]
