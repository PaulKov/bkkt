from __future__ import annotations

import argparse
from typing import List, Sequence


def add_repeatable_csv_arg(
    parser: argparse.ArgumentParser,
    *flags: str,
    dest: str,
    help: str,
) -> None:
    """Add a repeatable CLI option that also accepts comma-separated values."""

    parser.add_argument(*flags, dest=dest, action="append", default=None, help=help)


def split_repeatable_csv(values: Sequence[str] | None) -> List[str]:
    """Normalize repeatable/CSV argparse values while preserving order."""

    if not values:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in str(value).split(","):
            item = part.strip()
            if item and item not in seen:
                out.append(item)
                seen.add(item)
    return out
