from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from connectctl.services.audit.session import AuditSession
from connectctl.services.state.store import StateStore


def test_audit_session_redacts_sensitive_args_and_marks_success(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.sqlite")
    args = argparse.Namespace(
        env="prod",
        cluster="acme-main",
        password="secret",
        token="abc",
        names="orders-source",
    )

    with AuditSession(command="connect patch", args=args, store=store) as audit:
        audit.event("diff_hash", payload={"hash": "sha256:test"})

    run = store.query_runs(limit=1)[0]
    assert run.outcome == "success"
    assert run.args_summary["password"] == "***REDACTED***"
    assert run.args_summary["token"] == "***REDACTED***"
    assert run.args_summary["names"] == "orders-source"
    assert [event.event_type for event in store.query_events(run.id)] == [
        "command_started",
        "diff_hash",
        "command_finished",
    ]


def test_audit_session_marks_failure_on_exception(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.sqlite")

    with pytest.raises(RuntimeError, match="boom"):
        with AuditSession(
            command="apply",
            args=argparse.Namespace(env="prod", cluster="all"),
            store=store,
        ):
            raise RuntimeError("boom")

    run = store.query_runs(limit=1)[0]
    assert run.outcome == "failed"
    assert run.error == "boom"


def test_audit_session_marks_non_zero_result_code_as_failed(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.sqlite")

    with AuditSession(
        command="apply",
        args=argparse.Namespace(env="prod", cluster="cluster-a"),
        store=store,
    ) as audit:
        audit.set_result_code(2)

    run = store.query_runs(limit=1)[0]
    assert run.outcome == "failed"
    assert run.error == "command returned exit code 2"
