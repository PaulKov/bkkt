from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models import RepoConfig


def infer_connector_dir_scope_from_path(cfg: RepoConfig, path: Path) -> Optional[Path]:
    """Best-effort: infer connector_dir scope from any file path in the repo.

    We map any path under connectors_root to a connector_dir folder path:

        <domain>/<source|sink>/<system>/<connector_dir>

    This helper is used to implement "scope=changed" behaviour for repo-wide checks
    and migration tools (so CI can be incremental).

    Rules:
    - ignore paths outside connectors_root
    - ignore special folders at connector_dir level (types/modes)
    - ignore dot-folders

    Returns:
        Relative path (POSIX) from connectors_root to connector_dir folder, e.g.:
        Path("acme/source/postgres/connector_acme__orders")
    """

    p = Path(path)
    abs_p = p if p.is_absolute() else (cfg.root / p).resolve()
    root_abs = cfg.connectors_root.resolve()

    try:
        rel = abs_p.relative_to(root_abs)
    except Exception:
        return None

    parts = list(rel.parts)
    if len(parts) < 4:
        return None

    domain, ctype, system, connector_dir = parts[0], parts[1], parts[2], parts[3]
    if connector_dir in {"types", "modes"}:
        return None
    if connector_dir.startswith("."):
        return None

    return Path(domain) / ctype / system / connector_dir
