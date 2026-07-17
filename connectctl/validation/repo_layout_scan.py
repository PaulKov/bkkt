from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..models import RepoConfig


def iter_domain_dirs(cfg: RepoConfig) -> Iterable[Path]:
    """Iterate top-level domain directories under connectors_root."""

    root = cfg.connectors_root
    ignore = set(cfg.ignore_dirs)
    for p in root.iterdir():
        if not p.is_dir():
            continue
        if p.name.startswith("."):
            continue
        if p.name in ignore:
            continue
        yield p
