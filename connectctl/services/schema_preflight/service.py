from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ...models import ConnectorManifest
from .allowlist import find_allowlist_entry
from .models import JsonObject, PreflightDecision, SchemaPreflightResult, SchemaRisk
from .rules import SchemaRiskRules


class SchemaPreflightService:
    """Analyze schema-affecting connector changes before live mutation."""

    def __init__(
        self,
        *,
        repo_allowlist: Sequence[Mapping[str, Any]] | None = None,
        rules: SchemaRiskRules | None = None,
    ) -> None:
        self._repo_allowlist = tuple(repo_allowlist or ())
        self._rules = rules or SchemaRiskRules()

    def analyze(
        self,
        *,
        manifest: ConnectorManifest,
        existing_config: Mapping[str, Any] | None,
        connectctl_meta: Mapping[str, Any] | None = None,
        candidate_schema_files: Mapping[str, Path] | None = None,
    ) -> SchemaPreflightResult:
        risks = self._allow_documented_risks(
            connector=manifest.name,
            risks=self._rules.analyze(
                manifest=manifest, existing_config=existing_config
            ),
            manifest_meta=connectctl_meta or {},
        )
        exact_checks = _load_candidate_schema_files(candidate_schema_files or {})
        decision = _decision_for(risks)
        mode = "mixed" if exact_checks else "risk-analyzer-only"
        return SchemaPreflightResult(
            connector=manifest.name,
            decision=decision,
            mode=mode,
            risks=risks,
            exact_checks=tuple(exact_checks),
        )

    def _allow_documented_risks(
        self,
        *,
        connector: str,
        risks: tuple[SchemaRisk, ...],
        manifest_meta: Mapping[str, Any],
    ) -> tuple[SchemaRisk, ...]:
        manifest_entries = _manifest_allowlist_entries(manifest_meta)
        entries = (*self._repo_allowlist, *manifest_entries)
        allowed: list[SchemaRisk] = []
        for risk in risks:
            entry = find_allowlist_entry(
                entries=entries,
                connector=connector,
                risk_id=risk.risk_id,
            )
            if entry is None:
                allowed.append(risk)
                continue
            allowed.append(
                SchemaRisk(
                    risk_id=risk.risk_id,
                    severity=risk.severity,
                    message=risk.message,
                    changed_keys=risk.changed_keys,
                    allowed=True,
                    allowlist_entry=entry,
                )
            )
        return tuple(allowed)


def _manifest_allowlist_entries(
    meta: Mapping[str, Any]
) -> tuple[Mapping[str, Any], ...]:
    raw = meta.get("schema_registry_preflight")
    if not isinstance(raw, Mapping):
        return ()
    entries = raw.get("allowlist")
    if isinstance(entries, Sequence) and not isinstance(entries, str):
        return tuple(item for item in entries if isinstance(item, Mapping))

    # Backward-compatible legacy exception shape.
    if raw.get("allow_in_place_nullable_migration"):
        return (
            {
                "connector": str(meta.get("name") or ""),
                "risk_id": "protobuf_nullable_semantics_change",
                "adr": raw.get("migration_plan"),
                "owner": raw.get("owner") or "unknown",
                "expires_at": raw.get("expires_at") or "2999-01-01",
                "reason": raw.get("reason"),
            },
        )
    return ()


def _load_candidate_schema_files(
    candidate_schema_files: Mapping[str, Path],
) -> tuple[JsonObject, ...]:
    checks: list[JsonObject] = []
    for subject, path in sorted(candidate_schema_files.items()):
        text = path.read_text(encoding="utf-8")
        checks.append(
            {
                "subject": subject,
                "path": str(path),
                "status": "candidate-schema-loaded",
                "bytes": len(text.encode("utf-8")),
            }
        )
    return tuple(checks)


def _decision_for(risks: tuple[SchemaRisk, ...]) -> PreflightDecision:
    if any(risk.severity == "block" and not risk.allowed for risk in risks):
        return PreflightDecision.block
    if risks:
        return PreflightDecision.warn
    return PreflightDecision.pass_
