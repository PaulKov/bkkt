from __future__ import annotations

import sys
from pathlib import Path

from ..exceptions import ConfigError


def _read_text_file_or_dash(path_or_dash: str) -> str:
    """Read text content from a file path or '-' (stdin).

    This helper is shared by patch payload readers (JSON / key=value).
    """

    src = (path_or_dash or "-").strip()
    if src == "-":
        if sys.stdin.isatty():
            raise ConfigError(
                "Expected input via stdin (use a pipe) or provide a file path"
            )
        raw = sys.stdin.read()
        if not (raw or "").strip():
            raise ConfigError("Got empty stdin")
        return raw

    p = Path(src)
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    if not p.exists():
        raise ConfigError(f"File not found: {p}")
    return p.read_text(encoding="utf-8")
