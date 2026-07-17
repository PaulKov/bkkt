from __future__ import annotations

from ...exporting import DetectedLayout, resolve_sink_export_collision
from .models import ExportFlags
from .runner_logging import relpath


def resolve_collision(
    *, repo, layout: DetectedLayout, name: str, flags: ExportFlags, repo_root, log
) -> DetectedLayout:
    layout2, info = resolve_sink_export_collision(
        repo=repo,
        layout=layout,
        connector_name=name,
        force=flags.force,
        enabled=flags.auto_index_suffix_on_collision,
    )

    if info and info.get("collision") and layout2.connector_dir != layout.connector_dir:
        rel_env = relpath(info.get("env_file"), repo_root=repo_root)
        log.warning(
            "collision: %s exists for %s; exporting %s into connector_dir=%s",
            rel_env,
            (info.get("existing_name") or "unknown"),
            name,
            layout2.connector_dir,
        )
        return layout2

    if info and info.get("collision") and not flags.auto_index_suffix_on_collision:
        rel_env = relpath(info.get("env_file"), repo_root=repo_root)
        log.warning(
            "collision: %s exists for %s; auto-suffix disabled; consider --connector-dir or --force",
            rel_env,
            (info.get("existing_name") or "unknown"),
        )

    return layout
