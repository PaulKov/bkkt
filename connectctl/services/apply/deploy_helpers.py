from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ...diffing import configs_equal
from ...exceptions import ValidationError
from ...kafka import KafkaMetricsClient
from ...logging_utils import get_logger
from ...models import ConnectorManifest


def maybe_bootstrap_catalog(
    manifest: ConnectorManifest,
    *,
    enabled: bool,
    dry_run: bool,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Best-effort Iceberg → Glue Data Catalog bootstrap.

    This helper is deliberately isolated from the deployer logic so that:
      - the deployer stays small/readable
      - unit tests can stub/skip this behavior

    Any exception is swallowed (logged as a warning). Deployment should proceed.
    """

    log = get_logger(logger)

    if not enabled or dry_run:
        return

    try:
        from ...iceberg import maybe_bootstrap_glue_database

        msg = maybe_bootstrap_glue_database(manifest, enabled=True)
        if msg:
            log.info("%s", msg)
    except Exception as e:
        log.warning("auto-catalog bootstrap skipped for %s: %s", manifest.name, e)


def should_skip_unchanged(
    manifest: ConnectorManifest,
    existing_config: Optional[Dict[str, str]],
    *,
    skip_if_unchanged: bool,
    force: bool,
    drop_if_exists: bool,
    logger: Optional[logging.Logger] = None,
) -> bool:
    """Return True if we can safely skip an apply due to no drift."""

    log = get_logger(logger)

    if not skip_if_unchanged or force or drop_if_exists:
        return False

    if existing_config is None:
        return False

    if configs_equal(manifest.config, existing_config):
        log.info("SKIP: %s is already up-to-date (no drift)", manifest.name)
        return True

    return False


def maybe_wait_for_healthy(
    connect: Any,
    name: str,
    *,
    wait_seconds: Optional[float],
    timeout_seconds: float,
    poll_interval_seconds: float,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Optionally wait for connector to reach a healthy state."""

    log = get_logger(logger)

    if wait_seconds is None:
        return

    st = connect.wait_for_healthy(
        name,
        initial_delay_s=float(wait_seconds),
        timeout_s=float(timeout_seconds),
        poll_interval_s=float(poll_interval_seconds),
    )
    log.info(
        "Status after deploy: %s => connector=%s tasks=%s",
        name,
        st.connector_state,
        list(st.task_states),
    )


def maybe_run_smoke_checks(
    manifest: ConnectorManifest,
    *,
    enabled: bool,
    strict: bool,
    kafka_metrics: Optional[KafkaMetricsClient],
    logger: Optional[logging.Logger] = None,
) -> None:
    """Optionally run best-effort smoke checks.

    Non-fatal by default. If `strict=True`, raises ValidationError on issues.
    """

    log = get_logger(logger)

    if not enabled or kafka_metrics is None:
        return

    from ...smoke import format_smoke_text, run_smoke_checks

    issues = run_smoke_checks(manifest, kafka=kafka_metrics)
    if not issues:
        return

    log.warning("%s", format_smoke_text(issues))
    if strict:
        raise ValidationError(
            f"Smoke checks failed for {manifest.name} (disable with --no-smoke or keep non-strict)."
        )
