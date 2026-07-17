from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Callable, Iterable

from ..app.context import CliContext
from ..exceptions import ConnectCtlError
from .base import Command


CommandHandler = Callable[[argparse.Namespace], int]


@dataclass(frozen=True)
class FuncCommand(Command):
    """Адаптер: функция + register_parser => OOP-команда."""

    _name: str
    _register_parser: Callable[[argparse._SubParsersAction], argparse.ArgumentParser]
    _handler: Callable[..., int]

    @property
    def name(self) -> str:
        return self._name

    def register(
        self, subparsers: argparse._SubParsersAction
    ) -> argparse.ArgumentParser:
        p = self._register_parser(subparsers)
        # Устанавливаем OOP-команду в defaults для диспатча.
        # Параллельно может оставаться `func=` для b/c, но в CLI мы используем _command.
        p.set_defaults(_command=self)
        return p

    def run(self, args: argparse.Namespace, ctx: CliContext) -> int:
        return int(self._handler(args, ctx=ctx, logger=ctx.logger))


class CommandGroup(Command):
    """Групповая команда (например, `connect`), содержащая подкоманды."""

    def __init__(
        self,
        *,
        name: str,
        help: str,
        build_parser: Callable[[argparse._SubParsersAction], argparse.ArgumentParser],
        subcommands: Iterable[Command],
        subdest: str,
    ) -> None:
        self._name = name
        self._help = help
        self._build_parser = build_parser
        self._subcommands = list(subcommands)
        self._subdest = subdest

    @property
    def name(self) -> str:
        return self._name

    def register(
        self, subparsers: argparse._SubParsersAction
    ) -> argparse.ArgumentParser:
        p = self._build_parser(subparsers)
        sub = p.add_subparsers(dest=self._subdest, required=True)
        for cmd in self._subcommands:
            cmd.register(sub)
        return p

    def run(self, args: argparse.Namespace, ctx: CliContext) -> int:
        # По идее не вызывается: у group required subcommand.
        raise ConnectCtlError(f"Не указана подкоманда для `{self._name}`")
