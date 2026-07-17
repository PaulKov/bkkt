from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ...exceptions import ValidationError
from ...models import ConnectorManifest
from ...settings_models import Settings
from ...var_preflight import DeployContextVarsPreflightService
from ...var_preflight.models import VarPreflightResult
from ...var_providers import VarProviderContext


@dataclass(frozen=True)
class ApplyVarsPreflightOptions:
    enabled: bool
    reason: str | None = None
    provider_contracts: tuple[str, ...] = ()
    secret_index: str | None = None


def run_apply_vars_preflight(
    *,
    settings: Settings,
    manifest: ConnectorManifest,
    provider_context: VarProviderContext | None,
    options: ApplyVarsPreflightOptions,
    logger: logging.Logger,
) -> VarPreflightResult | None:
    """Run apply-time vars preflight and raise on blocking issues."""

    if not options.enabled:
        logger.warning(
            "Vars preflight skipped for %s: %s",
            manifest.name,
            options.reason or "no reason provided",
        )
        return None

    result = DeployContextVarsPreflightService(settings).run(
        manifest=manifest,
        provider_context=provider_context,
        provider_contracts=_paths(options.provider_contracts),
        secret_index=options.secret_index,
    )
    errors = [issue for issue in result.issues if issue.severity == "error"]
    warnings = [issue for issue in result.issues if issue.severity == "warning"]
    if errors:
        issue_lines = "\n".join(
            f"- {issue.code}: {issue.message}"
            + (f" ({issue.source})" if issue.source else "")
            for issue in errors[:10]
        )
        if len(errors) > 10:
            issue_lines += f"\n- ... {len(errors) - 10} more error(s)"
        raise ValidationError(
            "Vars preflight blocked apply for "
            f"{manifest.name}: {len(errors)} error(s).\n"
            f"{issue_lines}\n"
            "Fix provider contracts/secrets, or use --no-vars-preflight "
            "with --vars-preflight-reason only for audited break-glass."
        )

    if warnings:
        logger.warning(
            "Vars preflight warnings for %s: warnings=%d provider_contracts=%d secret_refs=%d",
            manifest.name,
            len(warnings),
            len(result.provider_contracts),
            len(result.secret_refs),
        )
    else:
        logger.info(
            "Vars preflight ok for %s: provider_contracts=%d secret_refs=%d",
            manifest.name,
            len(result.provider_contracts),
            len(result.secret_refs),
        )
    return result


def _paths(paths: Sequence[str]) -> tuple[str | Path, ...]:
    return tuple(paths)
