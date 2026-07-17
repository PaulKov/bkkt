from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Set, Tuple

from ..ports import FileSystem

from .virtual_layers import resolve_layers_virtual


def build_layers_for_render_virtual(
    *,
    repo_root: Path,
    connectors_root: Path,
    info: Any,
    env_file: Path,
    planned_files: Mapping[Path, Any],
    fs: FileSystem | None = None,
    override_only_paths: Optional[Sequence[Path]] = None,
    base_file: Optional[Path] = None,
) -> Tuple[Path, ...]:
    planned_paths = set(planned_files.keys()) | {env_file.resolve()}
    all_layers = resolve_layers_virtual(
        repo_root=repo_root,
        connectors_root=connectors_root,
        info=info,
        env_file=env_file,
        planned_paths=planned_paths,
        fs=fs,
        base_file=base_file,
    )

    if override_only_paths is None or len(override_only_paths) == 0:
        return tuple(all_layers)

    layers: list[Path] = []
    allowed = {p.resolve() for p in override_only_paths}
    planned_set = {p.resolve() for p in planned_files.keys()}

    # Preserve caller-provided order for allowed overrides (even if not in default layer list).
    for p in override_only_paths:
        rp = p.resolve()
        if (
            (fs.exists(rp) if fs else rp.exists()) or rp in planned_set
        ) and rp not in layers:
            layers.append(rp)

    for lp in all_layers:
        if lp in planned_set or lp in allowed or lp == env_file.resolve():
            if lp not in layers:
                layers.append(lp)

    return tuple(layers)


def build_layers_for_render_virtual_with_sources(
    *,
    repo_root: Path,
    connectors_root: Path,
    info: Any,
    env_file: Path,
    planned_files: Mapping[Path, Any],
    fs: FileSystem | None = None,
    override_only_paths: Optional[Sequence[Path]] = None,
    base_file: Optional[Path] = None,
) -> Tuple[Path, ...]:
    planned_paths: Set[Path] = set(planned_files.keys())
    all_layers = resolve_layers_virtual(
        repo_root=repo_root,
        connectors_root=connectors_root,
        info=info,
        env_file=env_file,
        planned_paths=planned_paths,
        fs=fs,
        base_file=base_file,
    )

    if override_only_paths:
        return tuple(
            list(all_layers) + [Path(p).resolve() for p in override_only_paths]
        )
    return tuple(all_layers)
