from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ...exporting import export_connector_to_repo, matches_any_regexp
from ...logging_utils import get_logger
from ...ports import ConnectApi
from ...repo import ConnectorRepo
from .models import (
    ExportFilters,
    ExportFlags,
    ExportPlacementOverrides,
    ExportSelection,
    ExportVariants,
    IcebergScaffolding,
)
from .runner_collision import resolve_collision
from .runner_layout import passes_all_filters, resolve_layout
from .runner_logging import log_all_scope, log_exported
from .runner_name_validation import validate_export_name
from .scaffolding import scaffold_generic_variants, scaffold_iceberg_variants


@dataclass
class ExportRunner:
    """Операционный runner команды `export`.

    Код разнесён по SRP‑модулям:
    - runner_layout: autodetect + фильтры
    - runner_collision: коллизии sink export
    - runner_logging: форматирование сообщений

    Этот класс — оркестратор.
    """

    repo_root: Path
    repo: ConnectorRepo
    settings: object
    connect: ConnectApi
    logger: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        self.log = get_logger(self.logger)
        # Export writes into the same repo tree; protect collision resolution + writes.
        self._write_lock = threading.RLock()

    def run(
        self,
        *,
        env,
        selection: ExportSelection,
        filters: ExportFilters,
        placement_overrides: ExportPlacementOverrides,
        flags: ExportFlags,
        variants: ExportVariants,
        iceberg: IcebergScaffolding,
        override_only_paths: Optional[list[Path]] = None,
        name_overrides: Optional[dict[str, str]] = None,
        jobs: int = 1,
    ) -> tuple[int, int]:
        exported = 0
        skipped = 0

        name_overrides = dict(name_overrides or {})

        if selection.all:
            log_all_scope(log=self.log, selection=selection, filters=filters)

        def _export_one(remote_name: str) -> tuple[int, int]:
            # 1) Read remote config (network) — can be parallel.
            cfg = self.connect.get_config_optional(remote_name)
            if cfg is None:
                self.log.warning("skip (missing): %s", remote_name)
                return (0, 1)

            if filters.patterns and not matches_any_regexp(
                name=remote_name, config=cfg, patterns=filters.patterns
            ):
                return (0, 1)

            export_name = name_overrides.get(remote_name, remote_name)
            if export_name != remote_name:
                self.log.info("export rename: %s -> %s", remote_name, export_name)

            layout = resolve_layout(
                env=env,
                name=export_name,
                selection_all=selection.all,
                placement_overrides=placement_overrides,
                log=self.log,
            )
            if layout is None:
                return (0, 1)

            # Validate that the *repo* name is deployable and consistent with placement.
            try:
                validate_export_name(
                    export_name=export_name,
                    remote_name=remote_name,
                    env=env,
                    layout=layout,
                )
            except Exception as e:
                self.log.error("ERROR exporting %s: %s", remote_name, e)
                return (0, 1)

            # Apply --all filters: don't override placement, only filter out.
            if selection.all and not passes_all_filters(layout=layout, filters=filters):
                return (0, 1)

            # 2) Repo writes + collision resolution must be protected.
            with self._write_lock:
                try:
                    layout2 = resolve_collision(
                        repo=self.repo,
                        layout=layout,
                        name=export_name,
                        flags=flags,
                        repo_root=self.repo_root,
                        log=self.log,
                    )

                    written, _layers = export_connector_to_repo(
                        repo=self.repo,
                        connector_name=export_name,
                        remote_config=cfg,
                        layout=layout2,
                        dry_run=flags.dry_run,
                        force=flags.force,
                        reuse_overrides=flags.reuse_overrides,
                        save_diffs=flags.save_diffs,
                        override_only_paths=override_only_paths,
                    )
                    log_exported(
                        log=self.log,
                        remote_name=remote_name,
                        export_name=export_name,
                        layout=layout2,
                        written=written,
                    )

                    # Optional scaffolding: generic variants (modes/kinds/init-only)
                    scaffold_generic_variants(
                        repo=self.repo,
                        repo_root=self.repo_root,
                        layout=layout2,
                        connector_name=export_name,
                        remote_config=cfg,
                        variants=variants,
                        reuse_overrides=flags.reuse_overrides,
                        dry_run=flags.dry_run,
                        force=flags.force,
                        logger=self.log,
                    )

                    # Optional: also scaffold Iceberg sink variants
                    scaffold_iceberg_variants(
                        repo=self.repo,
                        repo_root=self.repo_root,
                        layout=layout2,
                        connector_name=export_name,
                        remote_config=cfg,
                        iceberg=iceberg,
                        reuse_overrides=flags.reuse_overrides,
                        dry_run=flags.dry_run,
                        force=flags.force,
                        logger=self.log,
                    )
                except Exception as e:
                    self.log.error("ERROR exporting %s: %s", remote_name, e)
                    return (0, 1)

            return (1, 0)

        names = list(selection.names)
        if jobs <= 1:
            results = [_export_one(n) for n in names]
        else:
            from ...execution import map_collect

            collected = map_collect(names, _export_one, jobs=jobs)
            results = []
            for r in collected:
                if r.error:
                    self.log.error("ERROR exporting %s: %s", r.item, r.error)
                    results.append((0, 1))
                else:
                    results.append(r.value or (0, 1))

        exported += sum(r[0] for r in results)
        skipped += sum(r[1] for r in results)

        return exported, skipped
