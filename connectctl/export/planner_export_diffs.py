from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

from ..repo import ConnectorRepo


def _build_export_diffs(
    *,
    repo: ConnectorRepo,
    remote_config: Mapping[str, Any],
    rendered_config: Mapping[str, Any],
    key_sources: Mapping[str, Path],
) -> Dict[str, Any]:
    """Построить структурированный diff для export-report.

    export_diffs показывает, какие ключи в remote отличаются от результата виртуального рендера
    и из какого override-файла пришло значение.
    """

    export_diffs: Dict[str, Any] = {}
    for k, remote_val in remote_config.items():
        if k in rendered_config and rendered_config.get(k) != remote_val:
            src = key_sources.get(k)
            if src is None:
                continue

            try:
                src_rel = str(src.relative_to(repo.cfg.root))
            except Exception:
                src_rel = str(src)

            export_diffs[k] = {
                "override_file": src_rel,
                "override_value": rendered_config.get(k),
                "exported_connector_value": remote_val,
            }
    for k, rendered_val in rendered_config.items():
        if k in remote_config:
            continue
        src = key_sources.get(k)
        if src is None:
            continue

        try:
            src_rel = str(src.relative_to(repo.cfg.root))
        except Exception:
            src_rel = str(src)

        export_diffs[k] = {
            "override_file": src_rel,
            "override_value": rendered_val,
            "exported_connector_value": None,
            "resolution": "accepted_unset_inherited_key",
        }
    return export_diffs


def _build_export_comments(
    delta: Mapping[str, Any], export_diffs: Mapping[str, Any]
) -> Dict[str, str]:
    """Собрать комментарии для ключей, которые реально попали в delta."""

    comments: Dict[str, str] = {}
    for key, meta in export_diffs.items():
        if key in delta:
            comments[key] = (
                f"override candidate: {meta.get('override_file')} -> {meta.get('override_value')}"
            )
    return comments
