from __future__ import annotations

from pathlib import Path

from connectctl.services.state.store import StateStore


def test_state_store_records_operation_events_and_snapshots(tmp_path: Path) -> None:
    db_path = tmp_path / "bkkt.sqlite"
    store = StateStore(db_path)
    store.initialize()

    run = store.create_run(
        command="connect patch",
        env="prod",
        cluster="acme-main",
        args_summary={"names": ["orders-source"], "dry_run": False},
        plan_hash="sha256:test",
    )
    event = store.append_event(
        run.id,
        event_type="schema_preflight",
        level="WARN",
        message="review required",
        payload={"risks": ["nullable_semantics_changed"]},
    )
    snapshot = store.put_snapshot(
        run.id,
        snapshot_type="live_config",
        name="orders-source",
        payload={"config": {"connector.class": "X"}},
    )
    finished = store.finish_run(run.id, outcome="success")

    assert finished.outcome == "success"
    assert event.run_id == run.id
    assert snapshot.run_id == run.id

    runs = store.query_runs(limit=10)
    assert [item.id for item in runs] == [run.id]
    assert runs[0].args_summary == {"names": ["orders-source"], "dry_run": False}

    events = store.query_events(run.id)
    assert [item.event_type for item in events] == ["schema_preflight"]
    assert events[0].payload == {"risks": ["nullable_semantics_changed"]}

    snapshots = store.query_snapshots(run.id)
    assert [item.name for item in snapshots] == ["orders-source"]
    assert snapshots[0].payload == {"config": {"connector.class": "X"}}

    doctor = store.doctor()
    assert doctor["ok"] is True
    assert doctor["runs"] == 1
    assert doctor["events"] == 1
    assert doctor["snapshots"] == 1
