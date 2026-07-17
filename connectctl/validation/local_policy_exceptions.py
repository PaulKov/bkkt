from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from ..models import ConnectorManifest
from .policies_models import PolicyIssue

_CROSS_ENV_POLICIES = {
    "BOOTSTRAP_HARDCODED",
    "SCHEMA_REGISTRY_HARDCODED",
    "FOREIGN_ENV_REFERENCE",
}


def accepted_policy_exception_reason(
    *,
    manifest: ConnectorManifest,
    issue: PolicyIssue,
) -> Optional[str]:
    """Return reason for a documented local policy exception, if any."""

    if issue.policy not in _CROSS_ENV_POLICIES:
        return None

    drift_path = Path(manifest.source_path).parent / "export" / "drift.yaml"
    if not drift_path.exists():
        return None

    try:
        payload = yaml.safe_load(drift_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("connector_name_repo") != manifest.name:
        return None

    live_env = str(payload.get("env") or "").strip()
    repo_env = str(payload.get("repo_env") or manifest.info.env.value).strip()
    if not live_env or not repo_env or live_env == repo_env:
        return None

    return (
        "documented cross-env live mapping from export/drift.yaml; "
        "repo wrapper intentionally preserves live behavior"
    )
