from __future__ import annotations

import logging
from typing import Dict, Optional

from ...exceptions import ConnectApiError
from ...logging_utils import get_logger
from ...models import ConnectorManifest


def maybe_rollback_after_failure(
    connect,
    manifest: ConnectorManifest,
    *,
    enabled: bool,
    did_upsert: bool,
    prev_config: Optional[Dict[str, str]],
    original_error: Exception,
    wait_seconds: Optional[float],
    timeout_seconds: float,
    poll_interval_seconds: float,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Attempt a rollback after a failed deploy.

    Rollback is best-effort. If rollback itself fails, we raise ConnectApiError
    with both the original error and rollback error.
    """

    log = get_logger(logger)

    if not enabled or not did_upsert:
        return

    try:
        if prev_config is None:
            log.warning("ROLLBACK: deleting newly created connector: %s", manifest.name)
            connect.delete(manifest.name)
        else:
            log.warning("ROLLBACK: restoring previous config for: %s", manifest.name)
            rollback_manifest = type(manifest)(
                name=manifest.name,
                config=prev_config,
                source_path=manifest.source_path,
                info=manifest.info,
            )
            connect.upsert(rollback_manifest)

            if wait_seconds is not None:
                connect.wait_for_healthy(
                    manifest.name,
                    initial_delay_s=float(wait_seconds),
                    timeout_s=float(timeout_seconds),
                    poll_interval_s=float(poll_interval_seconds),
                )

    except Exception as rb:
        raise ConnectApiError(
            f"Deploy failed for {manifest.name}: {original_error}. Rollback also failed: {rb}"
        ) from rb


def maybe_drop_if_failed(
    connect,
    name: str,
    *,
    enabled: bool,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Optionally delete the connector if it ended up in FAILED state."""

    log = get_logger(logger)

    if not enabled:
        return

    try:
        st_now = connect.get_status(name)
        if st_now.connector_state == "FAILED" or any(
            ts == "FAILED" for ts in st_now.task_states
        ):
            log.warning(
                "DROP: deleting connector due to FAILED status (--drop-if-failed): %s",
                name,
            )
            connect.delete(name)
    except Exception as drop_e:
        log.warning("drop-if-failed could not check/delete %s: %s", name, drop_e)
