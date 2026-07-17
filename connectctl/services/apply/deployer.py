"""Connector deploy implementation.

This module is intentionally kept as a *backwards-compatible facade*.

Historically it contained the whole apply-side effect pipeline (~250 LOC).
As the project grew, this became hard to maintain, so it was split into
small SRP helpers:

  - deploy_options.py    (ApplyOptions)
  - deploy_helpers.py    (skip-if-unchanged, optional wait, smoke checks, auto-catalog)
  - deploy_rollback.py   (rollback-on-fail, drop-if-failed)

Public API remains the same:

  from connectctl.services.apply.deployer import ApplyOptions, ConnectorDeployer
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from ...ports import ConnectApi, FileSystem
from ...adapters.filesystem import LocalFileSystem
from ...logging_utils import get_logger
from ...models import ConnectorManifest
from ...kafka import KafkaMetricsClient

from .artifacts import write_rendered_artifact, write_rollback_artifact
from .deploy_helpers import (
    maybe_bootstrap_catalog,
    maybe_run_smoke_checks,
    maybe_wait_for_healthy,
    should_skip_unchanged,
)
from .deploy_options import ApplyOptions
from .deploy_rollback import maybe_drop_if_failed, maybe_rollback_after_failure
from .schema_registry_preflight import run_schema_registry_preflight


@dataclass
class ConnectorDeployer:
    """Applies a rendered manifest to a Kafka Connect cluster."""

    connect: ConnectApi
    rendered_dir: Path
    options: ApplyOptions
    kafka_metrics: Optional[KafkaMetricsClient] = None
    schema_preflight_allowlist: Sequence[Mapping[str, Any]] = ()
    fs: FileSystem = field(default_factory=LocalFileSystem)
    logger: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        self.log = get_logger(self.logger)

    def deploy(
        self,
        manifest: ConnectorManifest,
        *,
        loaded_from_artifact: bool,
        connectctl_meta: dict[str, object] | None = None,
    ) -> None:
        """Deploy a single connector manifest."""

        maybe_bootstrap_catalog(
            manifest,
            enabled=self.options.auto_catalog,
            dry_run=self.options.dry_run,
            logger=self.log,
        )

        if self.options.dry_run:
            src = "artifact" if loaded_from_artifact else "render"
            self.log.info(
                "[DRY-RUN] Would apply (%s): %s from %s",
                src,
                manifest.name,
                manifest.source_path,
            )
            return

        self.log.info("Applying: %s (from %s)", manifest.name, manifest.source_path)

        existing_config = self.connect.get_config_optional(manifest.name)
        prev_config = existing_config if self.options.rollback_on_fail else None

        # Optional: drop existing connector before apply.
        if self.options.drop_if_exists and existing_config is not None:
            self.log.warning(
                "DROP: deleting existing connector before apply (--drop-if-exists): %s",
                manifest.name,
            )
            self.connect.delete(manifest.name)
            existing_config = None

        if should_skip_unchanged(
            manifest,
            existing_config,
            skip_if_unchanged=self.options.skip_if_unchanged,
            force=self.options.force,
            drop_if_exists=self.options.drop_if_exists,
            logger=self.log,
        ):
            write_rendered_artifact(self.rendered_dir, manifest, fs=self.fs)
            return

        if self.options.schema_preflight:
            run_schema_registry_preflight(
                manifest=manifest,
                existing_config=existing_config,
                connectctl_meta=connectctl_meta or {},
                repo_allowlist=self.schema_preflight_allowlist,
            )
        else:
            self.log.warning(
                "Schema Registry preflight disabled for %s. Reason: %s",
                manifest.name,
                self.options.schema_preflight_reason,
            )

        did_upsert = False
        try:
            if self.options.connect_validate:
                self.connect.validate_manifest(manifest)

            self.connect.upsert(manifest)
            did_upsert = True

            write_rendered_artifact(self.rendered_dir, manifest, fs=self.fs)

            maybe_wait_for_healthy(
                self.connect,
                manifest.name,
                wait_seconds=self.options.wait_seconds,
                timeout_seconds=self.options.timeout_seconds,
                poll_interval_seconds=self.options.poll_interval_seconds,
                logger=self.log,
            )

            maybe_run_smoke_checks(
                manifest,
                enabled=self.options.smoke,
                strict=self.options.smoke_strict,
                kafka_metrics=self.kafka_metrics,
                logger=self.log,
            )

        except Exception as e:
            rollback_artifact = write_rollback_artifact(
                self.rendered_dir,
                manifest,
                previous_config=prev_config,
                desired_config=manifest.config,
                error=e,
                fs=self.fs,
            )
            self.log.warning("Rollback artifact written: %s", rollback_artifact)
            maybe_rollback_after_failure(
                self.connect,
                manifest,
                enabled=self.options.rollback_on_fail,
                did_upsert=did_upsert,
                prev_config=prev_config,
                original_error=e,
                wait_seconds=self.options.wait_seconds,
                timeout_seconds=self.options.timeout_seconds,
                poll_interval_seconds=self.options.poll_interval_seconds,
                logger=self.log,
            )

            maybe_drop_if_failed(
                self.connect,
                manifest.name,
                enabled=self.options.drop_if_failed,
                logger=self.log,
            )

            raise


__all__ = ["ApplyOptions", "ConnectorDeployer"]
