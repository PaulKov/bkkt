from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from ...exporting import apply_plan_to_repo, build_iceberg_sink_variants_planned_files
from ...logging_utils import get_logger
from ...models import ConnectorType
from ...repo import ConnectorRepo
from ..name_variants import sink_name_with_kind, source_name_with_mode
from .models import ExportVariants, IcebergScaffolding


def _log_written_files(
    *,
    repo_root: Path,
    written: Optional[Mapping[Path, Any]] | list[Path],
    logger: logging.Logger,
    prefix: str,
) -> None:
    if not written:
        logger.info("%s: ничего не записано (уже существует)", prefix)
        return

    paths = list(written)  # works for list[Path] and dict keys
    rels: list[str] = []
    for p in paths:
        try:
            rels.append(str(Path(p).relative_to(repo_root)))
        except Exception:
            rels.append(str(p))

    logger.info("%s: создано %s файл(ов): %s", prefix, len(rels), ", ".join(rels))


def scaffold_generic_variants(
    *,
    repo: ConnectorRepo,
    repo_root: Path,
    layout,
    connector_name: str,
    remote_config: Dict[str, Any],
    variants: ExportVariants,
    reuse_overrides: bool,
    dry_run: bool,
    force: bool,
    logger=None,
) -> None:
    """Создать дополнительные env-манифесты/overrides (modes/kinds/init-only) как `connectctl init`.

    Пишем *name-only* манифесты (без `config`) если включён `reuse_overrides`.
    """

    log = get_logger(logger)
    planned: Dict[Path, Dict[str, Any]] = {}

    target_dir = (
        repo.cfg.connectors_root
        / layout.domain
        / layout.connector_type.value
        / layout.system
        / layout.connector_dir
    )

    # Source: mode variants
    if layout.connector_type == ConnectorType.source and (
        variants.source_modes or variants.init_only
    ):
        for m in variants.source_modes:
            variant_name = source_name_with_mode(connector_name, m)
            if variant_name == connector_name:
                continue
            pth = (target_dir / f"{variant_name}.json").resolve()
            obj: Dict[str, Any] = {"name": variant_name}
            if not reuse_overrides:
                obj["config"] = dict(remote_config)
            planned[pth] = obj

        if variants.init_only:
            pth = (target_dir / "modes" / "init" / "all.json").resolve()
            planned[pth] = {"vars": {"debezium_snapshot_mode_init": "initial_only"}}

    # Sink: kind variants
    if layout.connector_type == ConnectorType.sink and variants.sink_kinds:
        for k in variants.sink_kinds:
            variant_name = sink_name_with_kind(connector_name, k)
            if variant_name == connector_name:
                continue
            pth = (target_dir / f"{variant_name}.json").resolve()
            obj = {"name": variant_name}
            if not reuse_overrides:
                obj["config"] = dict(remote_config)
            planned[pth] = obj

    if not planned:
        return

    written = apply_plan_to_repo(planned_files=planned, dry_run=dry_run, force=force)
    _log_written_files(
        repo_root=repo_root, written=written, logger=log, prefix="variants scaffolding"
    )


def scaffold_iceberg_variants(
    *,
    repo: ConnectorRepo,
    repo_root: Path,
    layout,
    connector_name: str,
    remote_config: Dict[str, Any],
    iceberg: IcebergScaffolding,
    reuse_overrides: bool,
    dry_run: bool,
    force: bool,
    logger=None,
) -> None:
    """Опционально создать дополнительные kinds для IcebergSinkConnector."""

    log = get_logger(logger)

    if not iceberg.kinds:
        return
    if not reuse_overrides:
        # В режиме raw-export не создаём iceberg overrides/variants (иначе получится смесь).
        return
    if (
        str(remote_config.get("connector.class") or "")
        != "io.tabular.iceberg.connect.IcebergSinkConnector"
    ):
        return
    if layout.connector_type != ConnectorType.sink:
        return

    planned = build_iceberg_sink_variants_planned_files(
        repo=repo,
        layout=layout,
        connector_name=connector_name,
        remote_config=remote_config,
        kinds=iceberg.kinds,
        generate_overrides=iceberg.generate_overrides,
        generate_manifests=iceberg.generate_manifests,
        table_id_columns=iceberg.table_id_columns or None,
    )
    written = apply_plan_to_repo(planned_files=planned, dry_run=dry_run, force=force)
    _log_written_files(
        repo_root=repo_root, written=written, logger=log, prefix="iceberg scaffolding"
    )
