from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ..exceptions import ConfigError
from ..repo import ConnectorRepo
from .virtual_renderer_fragments import collect_fragments
from .virtual_renderer_layers import (
    build_layers_for_render_virtual,
    build_layers_for_render_virtual_with_sources,
)
from .virtual_renderer_name import infer_name_from_filename
from .virtual_renderer_placeholders import resolve_placeholders_for_render


def render_virtual(
    *,
    repo: ConnectorRepo,
    env_file: Path,
    planned_files: Mapping[Path, Mapping[str, Any]],
    override_only_paths: Optional[Sequence[Path]] = None,
    fallback_name: Optional[str] = None,
) -> Tuple[str, Dict[str, Any], Tuple[Path, ...]]:
    """Отрендерить манифест, используя overrides репозитория + planned files, без записи на диск."""

    info = repo.parse_connector_path(env_file, must_exist=False)
    base_file = repo.find_base_file_for(env_file)

    layers = build_layers_for_render_virtual(
        repo_root=repo.cfg.root,
        connectors_root=repo.cfg.connectors_root,
        info=info,
        env_file=env_file,
        planned_files=planned_files,
        fs=repo.fs,
        override_only_paths=override_only_paths,
        base_file=base_file,
    )

    name, config, vars_ctx, _key_sources = collect_fragments(
        layers=layers,
        planned_files=planned_files,
        track_sources=False,
        fs=repo.fs,
    )

    if not name:
        name = infer_name_from_filename(env_file)
    if not name and fallback_name:
        name = fallback_name
    if not name:
        raise ConfigError(f"Rendered connector has empty 'name' for {env_file}")

    resolved_name, resolved_config = resolve_placeholders_for_render(
        info=info,
        name=str(name),
        config=config,
        vars_ctx=vars_ctx,
    )
    return resolved_name, resolved_config, tuple(layers)


def render_virtual_with_sources(
    *,
    repo: ConnectorRepo,
    env_file: Path,
    planned_files: Mapping[Path, Any],
    override_only_paths: Optional[Sequence[Path]] = None,
    base_file: Optional[Path] = None,
    fallback_name: Optional[str] = None,
) -> Tuple[str, Dict[str, Any], Tuple[Path, ...], Dict[str, Path]]:
    """Как :func:`render_virtual`, но возвращает ещё mapping ключа конфига → слой-источник."""

    info = repo.parse_connector_path(env_file, must_exist=False)
    layers = build_layers_for_render_virtual_with_sources(
        repo_root=repo.cfg.root,
        connectors_root=repo.cfg.connectors_root,
        info=info,
        env_file=env_file,
        planned_files=planned_files,
        fs=repo.fs,
        override_only_paths=override_only_paths,
        base_file=base_file,
    )

    name, config, vars_ctx, key_sources = collect_fragments(
        layers=layers,
        planned_files=planned_files,
        track_sources=True,
        fs=repo.fs,
    )

    if not name:
        name = infer_name_from_filename(env_file)
    if not name and fallback_name:
        name = fallback_name
    if not name:
        raise ConfigError(f"Rendered connector has empty 'name' for {env_file}")

    resolved_name, resolved_config = resolve_placeholders_for_render(
        info=info,
        name=str(name),
        config=config,
        vars_ctx=vars_ctx,
    )

    return resolved_name, resolved_config, tuple(layers), key_sources
