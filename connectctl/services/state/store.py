from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import uuid4

from .models import AuditEvent, JsonObject, OperationRun, SnapshotRecord


SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid4().hex


def _dump_json(value: JsonObject | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def _load_json(value: str | None) -> JsonObject:
    if not value:
        return {}
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else {"value": loaded}


class StateStore:
    """Durable SQLite audit store used by mutating core commands."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys = on")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                create table if not exists schema_migrations (
                    version integer primary key,
                    applied_at text not null
                );

                create table if not exists operation_runs (
                    id text primary key,
                    command text not null,
                    env text,
                    cluster text,
                    args_summary_json text not null,
                    plan_hash text,
                    outcome text,
                    error text,
                    started_at text not null,
                    finished_at text
                );

                create table if not exists audit_events (
                    id text primary key,
                    run_id text not null references operation_runs(id) on delete cascade,
                    event_type text not null,
                    level text not null,
                    message text not null,
                    payload_json text not null,
                    created_at text not null
                );

                create table if not exists snapshots (
                    id text primary key,
                    run_id text not null references operation_runs(id) on delete cascade,
                    snapshot_type text not null,
                    name text not null,
                    payload_json text not null,
                    created_at text not null
                );

                create index if not exists idx_audit_events_run_created
                    on audit_events(run_id, created_at);
                create index if not exists idx_snapshots_run_created
                    on snapshots(run_id, created_at);
                create index if not exists idx_operation_runs_started
                    on operation_runs(started_at);
                """
            )
            connection.execute(
                """
                insert or ignore into schema_migrations(version, applied_at)
                values (?, ?)
                """,
                (SCHEMA_VERSION, _now()),
            )

    def create_run(
        self,
        *,
        command: str,
        env: str | None = None,
        cluster: str | None = None,
        args_summary: JsonObject | None = None,
        plan_hash: str | None = None,
    ) -> OperationRun:
        self.initialize()
        run = OperationRun(
            id=_new_id(),
            command=command,
            env=env,
            cluster=cluster,
            args_summary=args_summary or {},
            plan_hash=plan_hash,
            outcome=None,
            error=None,
            started_at=_now(),
            finished_at=None,
        )
        with self._connect() as connection:
            connection.execute(
                """
                insert into operation_runs(
                    id, command, env, cluster, args_summary_json, plan_hash,
                    outcome, error, started_at, finished_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.id,
                    run.command,
                    run.env,
                    run.cluster,
                    _dump_json(run.args_summary),
                    run.plan_hash,
                    run.outcome,
                    run.error,
                    run.started_at,
                    run.finished_at,
                ),
            )
        return run

    def append_event(
        self,
        run_id: str,
        *,
        event_type: str,
        level: str = "INFO",
        message: str = "",
        payload: JsonObject | None = None,
    ) -> AuditEvent:
        self.initialize()
        event = AuditEvent(
            id=_new_id(),
            run_id=run_id,
            event_type=event_type,
            level=level,
            message=message,
            payload=payload or {},
            created_at=_now(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                insert into audit_events(
                    id, run_id, event_type, level, message, payload_json, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.run_id,
                    event.event_type,
                    event.level,
                    event.message,
                    _dump_json(event.payload),
                    event.created_at,
                ),
            )
        return event

    def put_snapshot(
        self,
        run_id: str,
        *,
        snapshot_type: str,
        name: str,
        payload: JsonObject | None = None,
    ) -> SnapshotRecord:
        self.initialize()
        snapshot = SnapshotRecord(
            id=_new_id(),
            run_id=run_id,
            snapshot_type=snapshot_type,
            name=name,
            payload=payload or {},
            created_at=_now(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                insert into snapshots(
                    id, run_id, snapshot_type, name, payload_json, created_at
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.id,
                    snapshot.run_id,
                    snapshot.snapshot_type,
                    snapshot.name,
                    _dump_json(snapshot.payload),
                    snapshot.created_at,
                ),
            )
        return snapshot

    def finish_run(
        self,
        run_id: str,
        *,
        outcome: str,
        error: str | None = None,
    ) -> OperationRun:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """
                update operation_runs
                set outcome = ?, error = ?, finished_at = ?
                where id = ?
                """,
                (outcome, error, _now(), run_id),
            )
        run = self.get_run(run_id)
        if run is None:
            raise KeyError(f"operation run not found: {run_id}")
        return run

    def get_run(self, run_id: str) -> OperationRun | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "select * from operation_runs where id = ?",
                (run_id,),
            ).fetchone()
        return None if row is None else _row_to_run(row)

    def query_runs(
        self,
        *,
        limit: int = 20,
        outcome: str | None = None,
    ) -> tuple[OperationRun, ...]:
        self.initialize()
        safe_limit = max(1, int(limit))
        with self._connect() as connection:
            if outcome:
                rows = connection.execute(
                    """
                    select * from operation_runs
                    where outcome = ?
                    order by started_at desc, rowid desc
                    limit ?
                    """,
                    (outcome, safe_limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    select * from operation_runs
                    order by started_at desc, rowid desc
                    limit ?
                    """,
                    (safe_limit,),
                ).fetchall()
        return tuple(_row_to_run(row) for row in rows)

    def query_events(self, run_id: str) -> tuple[AuditEvent, ...]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                select * from audit_events
                where run_id = ?
                order by created_at asc, rowid asc
                """,
                (run_id,),
            ).fetchall()
        return tuple(_row_to_event(row) for row in rows)

    def query_snapshots(self, run_id: str) -> tuple[SnapshotRecord, ...]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                select * from snapshots
                where run_id = ?
                order by created_at asc, rowid asc
                """,
                (run_id,),
            ).fetchall()
        return tuple(_row_to_snapshot(row) for row in rows)

    def doctor(self) -> JsonObject:
        self.initialize()
        with self._connect() as connection:
            migrations = [
                int(row["version"])
                for row in connection.execute(
                    "select version from schema_migrations order by version"
                ).fetchall()
            ]
            runs = int(
                connection.execute("select count(*) from operation_runs").fetchone()[0]
            )
            events = int(
                connection.execute("select count(*) from audit_events").fetchone()[0]
            )
            snapshots = int(
                connection.execute("select count(*) from snapshots").fetchone()[0]
            )
        return {
            "ok": SCHEMA_VERSION in migrations,
            "db_path": str(self.db_path),
            "schema_version": SCHEMA_VERSION,
            "migrations": migrations,
            "runs": runs,
            "events": events,
            "snapshots": snapshots,
        }


def _row_to_run(row: sqlite3.Row) -> OperationRun:
    return OperationRun(
        id=str(row["id"]),
        command=str(row["command"]),
        env=row["env"],
        cluster=row["cluster"],
        args_summary=_load_json(row["args_summary_json"]),
        plan_hash=row["plan_hash"],
        outcome=row["outcome"],
        error=row["error"],
        started_at=str(row["started_at"]),
        finished_at=row["finished_at"],
    )


def _row_to_event(row: sqlite3.Row) -> AuditEvent:
    return AuditEvent(
        id=str(row["id"]),
        run_id=str(row["run_id"]),
        event_type=str(row["event_type"]),
        level=str(row["level"]),
        message=str(row["message"]),
        payload=_load_json(row["payload_json"]),
        created_at=str(row["created_at"]),
    )


def _row_to_snapshot(row: sqlite3.Row) -> SnapshotRecord:
    return SnapshotRecord(
        id=str(row["id"]),
        run_id=str(row["run_id"]),
        snapshot_type=str(row["snapshot_type"]),
        name=str(row["name"]),
        payload=_load_json(row["payload_json"]),
        created_at=str(row["created_at"]),
    )
