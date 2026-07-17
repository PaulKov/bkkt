from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..vars_contracts import VarsRedactor, VarsSchema, VarsSchemaEntry
from ..vars_contracts.models import VarsDoctorResult
from ..vars_contracts.validator import VarsSchemaValidator


@dataclass(frozen=True)
class TraceContractEnricher:
    """Adds typed vars contract metadata to trace payloads."""

    schema: VarsSchema

    def enrich_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        redactor = VarsRedactor(self.schema)
        steps = [dict(step) for step in payload.get("steps", []) or []]
        summary = {"variables": 0, "errors": 0, "warnings": 0}
        enriched_steps: list[dict[str, Any]] = []

        for step in steps:
            name = str(step.get("name") or "")
            raw_value = step.get("value")
            if step.get("kind") == "variable":
                summary["variables"] += 1
                contract = self._contract_for_variable(name, raw_value)
                summary["errors"] += sum(
                    1
                    for issue in contract.get("issues", [])
                    if issue.get("severity") == "error"
                )
                summary["warnings"] += sum(
                    1
                    for issue in contract.get("issues", [])
                    if issue.get("severity") == "warning"
                )
                step["contract"] = contract
            if "value" in step:
                step["value"] = redactor.redact_value(name, raw_value)
            enriched_steps.append(step)

        enriched = dict(payload)
        enriched["steps"] = enriched_steps
        enriched["contracts"] = {"summary": summary}
        return enriched

    def _contract_for_variable(self, key: str, value: Any) -> dict[str, Any]:
        entry = self._entry_by_key().get(key)
        if entry is None:
            return {
                "status": "missing",
                "type": None,
                "required": False,
                "sensitive": False,
                "deprecated": False,
                "replacement": None,
                "remove_after": None,
                "description": "",
                "issues": [],
            }

        result = self._validate_entry(entry, value)
        redactor = VarsRedactor(self.schema)
        issues = [
            redactor.redact_issue_payload(issue.to_payload()) for issue in result.issues
        ]
        return {
            "status": result.status,
            "type": entry.type,
            "required": entry.required,
            "sensitive": entry.sensitive,
            "deprecated": entry.deprecated,
            "replacement": entry.replacement,
            "remove_after": entry.remove_after,
            "description": entry.description,
            "issues": issues,
        }

    def _validate_entry(self, entry: VarsSchemaEntry, value: Any) -> VarsDoctorResult:
        values = {} if value is None else {entry.key: value}
        return VarsSchemaValidator().validate(
            VarsSchema(path=self.schema.path, entries=(entry,)),
            values,
        )

    def _entry_by_key(self) -> dict[str, VarsSchemaEntry]:
        return {entry.key: entry for entry in self.schema.entries}
