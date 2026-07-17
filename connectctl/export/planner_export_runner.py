from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ..models import ConnectorType
from ..repo import ConnectorRepo

from .iceberg import build_iceberg_sink_planned_files
from .layout import DetectedLayout
from .planner_delta import (
    compute_delta_for_remote_keys,
    compute_unset_keys_for_absent_remote,
)
from .planner_export_diffs import _build_export_comments, _build_export_diffs
from .planner_export_env import _find_planned_env_manifest
from .planner_export_report import (
    _allocate_export_report_path,
    build_export_report_payload,
)
from .planner_generic import build_generic_planned_files
from .planner_io import apply_plan_to_repo
from .virtual_render import render_virtual, render_virtual_with_sources


def export_connector_to_repo(
    *,
    repo: ConnectorRepo,
    connector_name: str,
    remote_config: Mapping[str, Any],
    layout: DetectedLayout,
    dry_run: bool,
    force: bool,
    reuse_overrides: bool,
    iceberg_generate_overrides: bool = True,
    iceberg_generate_manifests: bool = True,
    save_diffs: bool = False,
    override_only_paths: Optional[Sequence[Path]] = None,
) -> Tuple[list[Path], Tuple[Path, ...]]:
    """Экспортировать конфиг коннектора в репозиторий.

    При reuse_overrides=True мы выполняем виртуальный рендер, учитывая override-stack,
    и сохраняем только то, что необходимо для воспроизведения remote-коннектора.

    save_diffs=True:
      - сохраняем remote-значения даже при конфликте с overrides
      - пишем структурированный export-report в <connector_dir>/export/
    """

    planned_files = build_generic_planned_files(
        repo=repo,
        layout=layout,
        connector_name=connector_name,
        remote_config=remote_config,
    )

    env_file = _find_planned_env_manifest(planned_files, connector_name)

    # Raw export: кладём весь remote config прямо в env manifest
    if not reuse_overrides:
        planned_files[env_file.resolve()] = {
            "name": connector_name,
            "config": dict(remote_config),
        }

    # Iceberg helpers (sink/iceberg)
    if layout.connector_type == ConnectorType.sink and layout.system == "iceberg":
        if iceberg_generate_overrides:
            planned_files.update(
                build_iceberg_sink_planned_files(
                    repo=repo,
                    layout=layout,
                    connector_name=connector_name,
                    remote_config=remote_config,
                )
            )

    env_override_path = (env_file.parent / f"{layout.env.value}.json").resolve()
    layers_used: Tuple[Path, ...] = ()

    if reuse_overrides:
        _, rendered_config, layers_used, key_sources = render_virtual_with_sources(
            repo=repo,
            env_file=env_file,
            planned_files=planned_files,
            override_only_paths=override_only_paths,
            fallback_name=connector_name,
        )

        delta = compute_delta_for_remote_keys(
            rendered_config=rendered_config,
            remote_config=remote_config,
            include_different=save_diffs,
        )
        unset_keys = compute_unset_keys_for_absent_remote(
            rendered_config=rendered_config,
            remote_config=remote_config,
        )

        export_diffs = _build_export_diffs(
            repo=repo,
            remote_config=remote_config,
            rendered_config=rendered_config,
            key_sources=key_sources,
        )

        if delta or unset_keys:
            env_override_obj: Dict[str, Any] = {}
            if delta:
                env_override_obj["config"] = delta
            if unset_keys:
                env_override_obj["bkkt"] = {"unset_config_keys": list(unset_keys)}

            # При save_diffs добавляем комментарии только для ключей, которые реально попали в delta.
            if save_diffs and export_diffs:
                comments = _build_export_comments(delta, export_diffs) if delta else {}
                if comments:
                    env_override_obj["__export_comments__"] = comments

            planned_files[env_override_path] = env_override_obj

            # Перерендерим, чтобы наружу вернуть актуальный набор layers_used (включая новый planned файл).
            _, _, layers_used = render_virtual(
                repo=repo,
                env_file=env_file,
                planned_files=planned_files,
                override_only_paths=override_only_paths,
                fallback_name=connector_name,
            )

        if export_diffs:
            export_dir = (env_file.parent / "export").resolve()
            report_path, export_number = _allocate_export_report_path(
                export_dir=export_dir,
                connector_name=connector_name,
                fs=repo.fs,
            )

            planned_files[report_path] = dict(
                build_export_report_payload(
                    connector_name=connector_name,
                    env=layout.env.value,
                    export_number=export_number,
                    save_diffs=save_diffs,
                    export_diffs=export_diffs,
                )
            )
    written = apply_plan_to_repo(
        planned_files, dry_run=dry_run, force=force, fs=repo.fs
    )
    return written, layers_used
