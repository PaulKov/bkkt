from __future__ import annotations

from dataclasses import dataclass
from typing import Any


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class OperationRun:
    id: str
    command: str
    env: str | None
    cluster: str | None
    args_summary: JsonObject
    plan_hash: str | None
    outcome: str | None
    error: str | None
    started_at: str
    finished_at: str | None

    def to_payload(self) -> JsonObject:
        return {
            "id": self.id,
            "command": self.command,
            "env": self.env,
            "cluster": self.cluster,
            "args_summary": self.args_summary,
            "plan_hash": self.plan_hash,
            "outcome": self.outcome,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass(frozen=True)
class AuditEvent:
    id: str
    run_id: str
    event_type: str
    level: str
    message: str
    payload: JsonObject
    created_at: str

    def to_payload(self) -> JsonObject:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "event_type": self.event_type,
            "level": self.level,
            "message": self.message,
            "payload": self.payload,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class SnapshotRecord:
    id: str
    run_id: str
    snapshot_type: str
    name: str
    payload: JsonObject
    created_at: str

    def to_payload(self) -> JsonObject:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "snapshot_type": self.snapshot_type,
            "name": self.name,
            "payload": self.payload,
            "created_at": self.created_at,
        }
