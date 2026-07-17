from __future__ import annotations

import abc
import argparse

from ..app.context import CliContext


class Command(abc.ABC):
    """Абстракция CLI-команды.

    Цель: явный ООП-контракт для команд (без reflection-инъекции), удобный для расширения
    и тестирования.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Имя команды (как в CLI), например: `apply`, `diff`, `connect`"""

    @abc.abstractmethod
    def register(
        self, subparsers: argparse._SubParsersAction
    ) -> argparse.ArgumentParser:
        """Зарегистрировать argparse subparser и вернуть его."""

    @abc.abstractmethod
    def run(self, args: argparse.Namespace, ctx: CliContext) -> int:
        """Выполнить команду."""
