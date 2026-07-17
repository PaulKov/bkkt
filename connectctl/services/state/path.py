from __future__ import annotations

import os
from pathlib import Path


DEFAULT_STATE_DB = ".bkkt/state/bkkt.sqlite"
STATE_DB_ENV = "BKKT_STATE_DB"


def resolve_state_db_path(
    *, repo_root: Path, explicit_path: str | Path | None = None
) -> Path:
    raw = explicit_path or os.environ.get(STATE_DB_ENV) or DEFAULT_STATE_DB
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path
