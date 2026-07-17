from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from .models import FailureAnalysisContext, FailureRemediation


@dataclass(frozen=True)
class FailureBundlePayloadBuilder:
    def build(
        self,
        *,
        command: str,
        context: FailureAnalysisContext,
        created_at_iso: str,
        remediation: FailureRemediation,
        prepared_manifest: Optional[Mapping[str, Any]],
        routing_debug: Optional[Mapping[str, Any]],
    ) -> dict[str, Any]:
        return {
            "bundle_version": 1,
            "command": command,
            "env": context.env,
            "stage": context.stage,
            "created_at": created_at_iso,
            "error": {
                "type": context.error.__class__.__name__,
                "message": str(context.error),
            },
            "manifest": dict(context.manifest_meta),
            "routing": dict(context.routing_payload),
            "routing_debug": dict(routing_debug or {}),
            "pruned_config_keys": list(context.pruned_config_keys),
            "remediation": remediation.as_payload(),
            "files": {
                "prepared_manifest": (
                    "prepared_manifest.json" if prepared_manifest is not None else None
                ),
                "routing": (
                    "routing.json"
                    if context.routing_payload or routing_debug is not None
                    else None
                ),
                "readme": "README.md",
            },
            "extra": dict(context.extra),
        }
