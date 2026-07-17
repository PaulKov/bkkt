from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Mapping

from ..models import ConnectorType
from ..repo import ConnectorRepo

from .layout import DetectedLayout, build_sink_manifest_filename


def build_iceberg_sink_planned_files(
    *,
    repo: ConnectorRepo,
    layout: DetectedLayout,
    connector_name: str,
    remote_config: Mapping[str, Any],
) -> Dict[Path, Dict[str, Any]]:
    """Сгенерировать planned-файлы для Iceberg sink коннектора в DRY-layout.

    Важно: для non-flatten kinds мы намеренно НЕ экспортируем пер-table Iceberg настройки
    (iceberg.table.*), потому что обычно они нужны только для equality deletes/upserts.
    """
    if layout.connector_type != ConnectorType.sink:
        raise ValueError("layout must be sink")

    connectors_root = repo.cfg.connectors_root
    target_dir = (
        connectors_root / layout.domain / "sink" / layout.system / layout.connector_dir
    )

    env_file = target_dir / build_sink_manifest_filename(layout, connector_name)

    # Minimal env manifest (name only)
    planned: Dict[Path, Dict[str, Any]] = {}
    planned[env_file.resolve()] = {
        "name": connector_name,
    }

    # Shared connector-dir overrides
    dataset = layout.dataset or "CHANGE_ME"
    layer = layout.layer or "raw"

    topics = str(remote_config.get("topics") or remote_config.get("topics.regex") or "")
    # Best-effort make topics env/domain/dataset agnostic.
    # Example: cdc.prod.users.acme_common.acme.ma_users.0 -> cdc.${env}.${domain}.${dataset}.acme.ma_users.0
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

    # Kind-specific overrides (tasks.max, id-columns for flatten, custom kind suffix)
    kind = layout.kind or "default"

    kind_override: Dict[str, Any] = {"vars": {}, "config": {}}

    # tasks.max -> vars.sink.tasks_max
    tasks_max = remote_config.get("tasks.max")
    if tasks_max is not None and str(tasks_max).strip():
        kind_override.setdefault("vars", {}).setdefault("sink", {})["tasks_max"] = str(
            tasks_max
        )

    # id-columns / per-table config are typically required only for flatten-like connectors.
    # Put all iceberg.table.<db>.<table>.* keys into kind override ONLY for flatten.
    if kind == "flatten":
        table_prefix = "iceberg.table."
        for k, v in remote_config.items():
            if not isinstance(k, str):
                continue
            if not k.startswith(table_prefix):
                continue
            # Example: iceberg.table.<db>.<table__flatten>.id-columns
            m = re.match(r"^iceberg\.table\.([^.]+)\.([^.]+)\.(.+)$", k)
            if not m:
                continue
            _table = m.group(2)
            _rest = m.group(3)
            # Strip __flatten suffix when present, and add ${sink.table_suffix}.
            suffix = "__flatten"
            base_table = _table[: -len(suffix)] if _table.endswith(suffix) else _table
            new_key = f"iceberg.table.${{iceberg.db_name}}.{base_table}__${{sink.table_suffix}}.{_rest}"
            kind_override["config"][new_key] = v

    # Ensure suffix is set for non-default kinds if remote config had suffix set.
    if kind != "default":
        suffix_val = remote_config.get("transforms.setTableName.table.suffix")
        if suffix_val is not None:
            kind_override["config"]["transforms.setTableName.table.suffix"] = str(
                suffix_val
            )
        else:
            kind_override["config"][
                "transforms.setTableName.table.suffix"
            ] = "${sink.table_suffix}"

    # Write kind override only if we actually have something to put there.
    if kind_override.get("vars") or kind_override.get("config"):
        kind_path = (target_dir / "types" / kind / "all.json").resolve()
        planned[kind_path] = kind_override

    return planned
