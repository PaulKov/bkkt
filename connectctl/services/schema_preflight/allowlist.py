from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any


def find_allowlist_entry(
    *,
    entries: Sequence[Mapping[str, Any]],
    connector: str,
    risk_id: str,
) -> dict[str, Any] | None:
    for raw in entries:
        if not _matches(raw, connector=connector, risk_id=risk_id):
            continue
        if not _is_complete(raw):
            continue
        if _is_expired(raw.get("expires_at")):
            continue
        return dict(raw)
    return None


def _matches(raw: Mapping[str, Any], *, connector: str, risk_id: str) -> bool:
    if str(raw.get("risk_id") or "").strip() != risk_id:
        return False
    raw_connector = str(raw.get("connector") or "").strip()
    if raw_connector and raw_connector != connector:
        return False
    connectors = raw.get("connectors")
    if isinstance(connectors, Sequence) and not isinstance(connectors, str):
        return connector in {str(item).strip() for item in connectors}
    return bool(raw_connector)


def _is_complete(raw: Mapping[str, Any]) -> bool:
    return all(
        str(raw.get(key) or "").strip()
        for key in ("adr", "owner", "reason", "expires_at")
    )


def _is_expired(value: Any) -> bool:
    try:
        expiry = date.fromisoformat(str(value))
    except ValueError:
        return True
    return expiry < datetime.now(UTC).date()
