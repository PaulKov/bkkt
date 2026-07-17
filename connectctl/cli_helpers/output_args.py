from __future__ import annotations

import argparse

from ..output import OutputFormat


def add_output_format_args(
    parser: argparse.ArgumentParser, *, default: OutputFormat = OutputFormat.text
) -> None:
    """Добавить единые аргументы формата вывода для read-only команд.

    Стандарт BKKT:
      --output text|json|yaml  (default: text)

    Backward-compatible alias:
      --json  == --output json
    """

    parser.add_argument(
        "--output",
        choices=[f.value for f in OutputFormat],
        default=None,
        help=(
            "Формат вывода результата в stdout (text|json|yaml). "
            f"По умолчанию: {default.value}"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Alias для --output json (устаревает, используйте --output json)",
    )
