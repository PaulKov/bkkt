from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Dict, Optional, Sequence

from ...rendering.json_loader import load_json_file, normalize_fragment


def last_config_key_sources(layer_paths: Sequence[Path]) -> Dict[str, Path]:
    """Return mapping config_key -> last layer path that defines this key.

    Best-effort: ignores JSON parsing errors.
    """

    out: Dict[str, Path] = {}
    for lp in layer_paths:
        try:
            obj = load_json_file(lp)
            frag = normalize_fragment(obj)
        except Exception:
            continue

        cfg = frag.get("config")
        if isinstance(cfg, dict):
            for k in cfg.keys():
                out[str(k)] = lp

    return out


def count_override_sources_for_drift_keys(
    *,
    diff_keys: Sequence[str],
    key_sources: Dict[str, Path],
    repo_root: Path,
    env_file: Path,
    base_file: Optional[Path],
    counter: Counter[str],
) -> None:
    """Update counter for override layer files responsible for drift keys.

    Excludes the env manifest and the base manifest (focuses on shared overrides).
    """

    env_abs = env_file.resolve()
    base_abs = base_file.resolve() if base_file else None

    for k in diff_keys:
        lp = key_sources.get(k)
        if not lp:
            continue

        lp_abs = lp.resolve()
        if lp_abs == env_abs or (base_abs and lp_abs == base_abs):
            continue

        rel_lp = (
            str(lp_abs.relative_to(repo_root))
            if repo_root in lp_abs.parents
            else str(lp_abs)
        )
        counter[rel_lp] += 1
