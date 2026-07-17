from __future__ import annotations

import argparse
from typing import Callable

from ...cli_helpers.output_args import add_output_format_args


def register_parser(
    subparsers: argparse._SubParsersAction,
    *,
    handler: Callable[[argparse.Namespace], int],
) -> argparse.ArgumentParser:
    s = subparsers.add_parser("plan", help="Посчитать, что apply/delete по git diff")
    s.add_argument("--env", required=True, help="Окружение (dev|stage|prod)")
    s.add_argument("--base", help="Base git sha (по умолчанию: auto)")
    s.add_argument("--head", help="Head git sha (по умолчанию: auto)")
    add_output_format_args(s)
    s.set_defaults(func=handler)
    return s
