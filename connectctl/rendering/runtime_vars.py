from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

from ..logging_utils import get_logger

# Реализация runtime vars уже разбита по модулям `cli_helpers/runtime_vars_*`.
# Этот файл даёт публичный API без "_" для сервисов и команд.
from ..cli_helpers.runtime_vars_load import (
    _load_runtime_vars,
    _load_runtime_vars_with_sources,
    _print_vars_used,
)


def load_runtime_vars(args: Any, repo_root: Path) -> Dict[str, str]:
    """Загрузить runtime vars (без provenance)."""

    return _load_runtime_vars(args, repo_root)


def load_runtime_vars_with_sources(
    args: Any, repo_root: Path
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Загрузить runtime vars и provenance (источник каждого ключа)."""

    return _load_runtime_vars_with_sources(args, repo_root)


def log_vars_used(rr: Any, repo_root: Path, *, logger=None) -> None:
    """Логирует (stderr) список использованных переменных и их источники."""

    log = get_logger(logger)
    _print_vars_used(rr, repo_root, logger=log)
