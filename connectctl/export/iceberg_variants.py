from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ..exceptions import ConfigError
from ..models import ConnectorType
from ..repo import ConnectorRepo

from .iceberg_base import (
    infer_flatten_id_columns_from_remote,
    rewrite_iceberg_sink_name_kind,
)
from .layout import DetectedLayout, build_sink_manifest_filename


def build_iceberg_sink_variants_planned_files(
    *,
    repo: ConnectorRepo,
    layout: DetectedLayout,
    connector_name: str,
    remote_config: Mapping[str, Any],
    kinds: Sequence[str],
    generate_overrides: bool = True,
    generate_manifests: bool = True,
    table_id_columns: Optional[Mapping[str, str]] = None,
) -> Dict[Path, Dict[str, Any]]:
    """Сгенерировать planned-файлы для нескольких sink kinds (default/events/flatten/...).

    Используется в `connectctl export`, чтобы из одного существующего Iceberg sink
    быстро “наскэффолдить” дополнительные варианты (например events и flatten).

    Для flatten требуется id-columns. Мы пытаемся вытащить их из remote config,
    а если не получилось — можно передать через table_id_columns.
    """
    if layout.connector_type != ConnectorType.sink:
        raise ValueError("layout must be sink")

    # Normalize & de-duplicate kinds while preserving order
    norm_kinds: List[str] = []
    seen = set()
    for k in kinds:
        kk = (k or "").strip()
        if not kk:
            continue
        if kk not in seen:
            norm_kinds.append(kk)
            seen.add(kk)
    if not norm_kinds:
        norm_kinds = [layout.kind or "default"]

    connectors_root = repo.cfg.connectors_root
    target_dir = (
        connectors_root / layout.domain / "sink" / layout.system / layout.connector_dir
    )

    planned: Dict[Path, Dict[str, Any]] = {}

    # Shared connector-dir overrides
    if generate_overrides:
        dataset = layout.dataset or "CHANGE_ME"
        layer = layout.layer or "raw"

        topics = str(
            remote_config.get("topics") or remote_config.get("topics.regex") or ""
        )
        if topics:
            topics = topics.replace(
                f"cdc.{layout.env.value}.{layout.domain}.{dataset}.",
                "cdc.${env}.${domain}.${dataset}.",
            )

        all_override: Dict[str, Any] = {
            "vars": {
                "dataset": dataset,
                "layer": layer,
                "iceberg": {
                    "db_name": "${env}__dbt__${domain}__${dataset}__${layer}",
                    "warehouse": "s3://${s3.bucket}/iceberg/lakehouse/dbt/${domain}/${dataset}/${layer}",
                },
            },
            "config": {},
        }
        if "topics" in remote_config:
            all_override["config"]["topics"] = topics
        elif "topics.regex" in remote_config:
            all_override["config"]["topics.regex"] = topics

        all_path = (target_dir / "all.json").resolve()
        planned[all_path] = all_override

    # Flatten id-columns input
    inferred_id_cols = infer_flatten_id_columns_from_remote(remote_config)
    merged_id_cols: Dict[str, str] = {}
    merged_id_cols.update(inferred_id_cols)
    if table_id_columns:
        merged_id_cols.update({str(k): str(v) for k, v in table_id_columns.items()})

    # Per-kind env manifest + type overrides
    for kind in norm_kinds:
        kind_norm = kind or "default"
        if kind_norm == "":
            kind_norm = "default"

        layout_k = DetectedLayout(**{**layout.__dict__, "kind": kind_norm})
        name_k = rewrite_iceberg_sink_name_kind(connector_name, kind_norm)

        if generate_manifests:
            env_file = (
                target_dir / build_sink_manifest_filename(layout_k, name_k)
            ).resolve()
            planned[env_file] = {
                "name": name_k,
            }

        if not generate_overrides:
            continue

        kind_override: Dict[str, Any] = {"vars": {}, "config": {}}

        # tasks.max -> vars.sink.tasks_max
        tasks_max = remote_config.get("tasks.max")
        if tasks_max is not None and str(tasks_max).strip():
            kind_override.setdefault("vars", {}).setdefault("sink", {})["tasks_max"] = (
                str(tasks_max)
            )

        # Always rely on ${sink.table_suffix} for variants.
        if kind_norm != "default":
            kind_override["config"][
                "transforms.setTableName.table.suffix"
            ] = "${sink.table_suffix}"

        # Flatten needs id-columns.
        if kind_norm == "flatten":
            if not merged_id_cols:
                raise ConfigError(
                    "Cannot generate flatten overrides: no iceberg.table.*.id-columns found in remote config and none provided via --iceberg-table-id-columns"
                )
            for table, cols in merged_id_cols.items():
                key = f"iceberg.table.${{iceberg.db_name}}.{table}__${{sink.table_suffix}}.id-columns"
                kind_override["config"][key] = cols

        if kind_override.get("vars") or kind_override.get("config"):
            kind_path = (target_dir / "types" / kind_norm / "all.json").resolve()
            planned[kind_path] = kind_override

    return planned
