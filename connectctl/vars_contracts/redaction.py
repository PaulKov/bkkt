from __future__ import annotations

from typing import Any, Mapping

from .models import VarsSchema


REDACTED_VALUE = "<redacted>"


class VarsRedactor:
    """Redacts variables marked sensitive in `bkkt/vars.schema.yaml`."""

    def __init__(self, schema: VarsSchema) -> None:
        self._sensitive_keys = frozenset(
            entry.key for entry in schema.entries if entry.sensitive
        )

    def is_sensitive(self, key: str) -> bool:
        return key in self._sensitive_keys

    def redact_value(self, key: str, value: Any) -> Any:
        if self.is_sensitive(key):
            return REDACTED_VALUE
        return value

    def redact_mapping(self, values: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: self.redact_value(key, value)
            for key, value in sorted(values.items(), key=lambda item: item[0])
        }

    def redact_issue_payload(self, issue: dict[str, Any]) -> dict[str, Any]:
        key = str(issue.get("key") or "")
        if not self.is_sensitive(key):
            return issue
        redacted = dict(issue)
        if "actual" in redacted:
            redacted["actual"] = REDACTED_VALUE
        return redacted
