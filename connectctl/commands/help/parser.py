from __future__ import annotations

import argparse
from typing import Callable


def register_parser(
    subparsers: argparse._SubParsersAction,
    *,
    handler: Callable[[argparse.Namespace], int],
) -> argparse.ArgumentParser:
    s = subparsers.add_parser(
        "help",
        help="Короткие примеры команд (шпаргалка из docs/CLI_EXAMPLES.md)",
    )
    s.add_argument(
        "topic",
        nargs="*",
        help="Тема/команда. Например: `help diff` или `help connect status` (по умолчанию: показать список тем)",
    )
    s.add_argument(
        "--list", action="store_true", help="Показать список доступных тем и выйти"
    )
    s.set_defaults(func=handler, requires_config=False)
    return s
