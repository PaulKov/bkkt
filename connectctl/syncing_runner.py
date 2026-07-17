from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .kafka.metrics import KafkaMetricsClient


from .ports import ConnectApi
from .ports import FileSystem
from .diffing import normalize_config
from .exceptions import RenderError, ValidationError
from .iceberg import ensure_iceberg_glue_database
from .logging_utils import get_logger
from .models import ConnectorManifest
from .syncing_models import SyncPlan


def run_sync(
    *,
    connect: ConnectApi,
    plan: SyncPlan,
    rendered_dir: Path,
    fs: FileSystem | None = None,
    dry_run: bool,
    wait_seconds: float,
    timeout_seconds: float,
    poll_interval_seconds: float,
    connect_validate: bool,
    rollback_on_fail: bool,
    skip_if_unchanged: bool = True,
    no_auto_catalog: bool = False,
    kafka: KafkaMetricsClient | None = None,
    smoke: bool = True,
    smoke_strict: bool = False,
    logger=None,
) -> None:
    """Apply the sync plan.

    - Writes rendered artifacts for each desired connector to rendered_dir.
    - Upserts desired connectors (unless dry_run or skip_if_unchanged triggers).
    - Prunes connectors if plan.to_delete is non-empty.
    - Optionally runs best-effort Kafka smoke checks (topics existence / sink lag).
    """

    log = get_logger(logger)

    (
        fs.mkdirs(rendered_dir, exist_ok=True)
        if fs
        else rendered_dir.mkdir(parents=True, exist_ok=True)
    )

    # Cache Glue DB create calls per (region, db_name)
    glue_cache: set[tuple[str, str]] = set()

    for name in plan.to_apply:
        manifest = plan.desired.get(name)
        if not manifest:
            raise RenderError(f"Missing desired manifest for {name}")

        # Always (re)write artifacts – they are useful even for no-op sync.
        payload = {"name": manifest.name, "config": manifest.config}
        out_path = rendered_dir / f"{manifest.name}.json"
        (
            fs.write_text(
                out_path,
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            if fs
            else out_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        )

        current_cfg: Optional[dict] = None
        if rollback_on_fail or skip_if_unchanged:
            current_cfg = connect.get_config_optional(name)

        # Drift-skip / no-op
        if skip_if_unchanged and current_cfg is not None:
            if normalize_config(current_cfg) == normalize_config(manifest.config):
                log.info(" - unchanged: %s (skip upsert)", name)
                continue

        if dry_run:
            log.info(" - would apply: %s", name)
            continue

        # Optional Iceberg Glue database bootstrap (default enabled)
        if not no_auto_catalog:
            try:
                created = ensure_iceberg_glue_database(
                    manifest, dry_run=False, cache=glue_cache
                )
                if created:
                    log.info(" - glue: ensured database for %s", name)
            except Exception:
                # Treat as a hard error because connector will likely fail without DB.
                raise

        prev_config = current_cfg if rollback_on_fail else None

        try:
            if connect_validate:
                connect.validate_manifest(manifest)
            connect.upsert(manifest)
            log.info(" - applied: %s", name)

            if wait_seconds > 0:
                connect.wait_for_healthy(
                    name,
                    initial_delay_s=wait_seconds,
                    timeout_s=timeout_seconds,
                    poll_interval_s=poll_interval_seconds,
                )

            # Best-effort smoke checks (non-fatal by default)
            if smoke and kafka is not None:
                from .smoke import format_smoke_text, run_smoke_checks

                issues = run_smoke_checks(manifest, kafka=kafka)
                if issues:
                    log.warning("%s", format_smoke_text(issues))
                    if smoke_strict:
                        raise ValidationError(
                            f"Smoke checks failed for {name} (enable --no-smoke to skip)"
                        )

        except Exception as e:
            log.error("ERROR applying %s: %s", name, e)
            if rollback_on_fail and prev_config is not None:
                try:
                    rollback_manifest = ConnectorManifest(
                        name=manifest.name,
                        config=prev_config,
                        source_path=manifest.source_path,
                        info=manifest.info,
                    )
                    connect.upsert(rollback_manifest)
                    log.warning("Rolled back %s to previous config", name)
                except Exception as re:
                    log.error("Rollback failed for %s: %s", name, re)
            raise

    # Prune
    for name in plan.to_delete:
        if dry_run:
            log.info(" - would prune: %s", name)
            continue

        try:
            connect.delete(name)
            log.info(" - pruned: %s", name)
        except Exception as e:
            log.error("ERROR pruning %s: %s", name, e)
            raise
