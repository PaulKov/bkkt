from __future__ import annotations

import logging
import sys
from typing import Optional


DEFAULT_LOGGER_NAME = "BKKT LOG"


def setup_logging(*, level: int = logging.INFO, force: bool = False) -> logging.Logger:
    """Configure default console logging.

    BKKT — CLI тулза. Для человеко‑читаемого вывода используйте logging (а не прямой вывод в stdout).

    Для машинного вывода (например `--output json|yaml`) используйте stdout, чтобы логи оставались в stderr.

    Notes:
    - We use a constant prefix "BKKT LOG" in the log format so that logs are easy to grep.
    - By default, output goes to stderr (safe for piping stdout into other tools).
    """
    root = logging.getLogger()
    if root.handlers and not force:
        return logging.getLogger(DEFAULT_LOGGER_NAME)

    # Reset handlers if force=True (or if handlers existed but we want a predictable config).
    if force:
        for h in list(root.handlers):
            root.removeHandler(h)

    handler = logging.StreamHandler(stream=sys.stderr)
    formatter = logging.Formatter("BKKT LOG | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)

    root.setLevel(level)
    root.addHandler(handler)

    # Create a named logger as a default DI target.
    return logging.getLogger(DEFAULT_LOGGER_NAME)


def get_logger(logger: Optional[logging.Logger] = None) -> logging.Logger:
    """Return a logger for DI.

    If `logger` is None, returns the default BKKT logger.
    """
    return logger if logger is not None else logging.getLogger(DEFAULT_LOGGER_NAME)
