"""Helpers for parsing ``--clusters`` style CLI arguments.

Several commands support selecting multiple Kafka Connect cluster groups.
Argparse can return:

- ``None``               (flag not used)
- ``"all"`` or ``"*"``   (explicit keyword)
- ``"a,b"``              (comma-separated)
- ``[]``                 (rare: nargs='*' and flag used without values)
- ``["a", "b"]``         (nargs='*' variant)

We normalize all those shapes to a list of strings.
"""

from __future__ import annotations
from typing import Iterable, List, Optional

from .selectors import _split_names_csv


def normalize_clusters_arg(raw) -> Optional[List[str]]:
    """Normalize argparse value of ``--clusters`` to a list of strings.

    Supported shapes:
    - None
    - str
    - list[str]
    """

    if raw is None:
        return None

    if isinstance(raw, list):
        if not raw:
            # argparse may return [] for flags like: --clusters (nargs='*')
            return ["all"]
        return [str(x) for x in raw]

    return [str(raw)]


def parse_clusters_selection(
    raw,
    *,
    available: Iterable[str],
    allow_all_keyword: bool = True,
) -> Optional[List[str]]:
    """Parse the value of ``--clusters`` into an explicit list of cluster groups.

    Returns:
        - None if the flag was not used (no filtering)
        - list[str] if filter is requested

    Notes:
        - Keyword ``all`` (or ``*``) expands to all available cluster groups.
        - A single string may contain comma-separated names.
    """

    items = normalize_clusters_arg(raw)
    if items is None:
        return None

    items_norm = [x.strip() for x in items if str(x).strip()]
    if not items_norm:
        return []

    if (
        allow_all_keyword
        and len(items_norm) == 1
        and items_norm[0].lower() in {"all", "*"}
    ):
        return sorted(list(available))

    # Common case: "a,b,c"
    if len(items_norm) == 1:
        return _split_names_csv(items_norm[0])

    # nargs='*' form: "a b c"
    return items_norm
