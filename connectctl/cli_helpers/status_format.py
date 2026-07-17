from __future__ import annotations

import json
from typing import Any, Dict, List

from ..models import ConnectorStatus
from ..services.operator.runbooks import RunbookRouter


def status_to_payload(
    st: ConnectorStatus, *, mode: str, include_raw: bool = False
) -> Dict[str, Any]:
    """Convert ConnectorStatus to a JSON-serializable dict.

    mode:
      - short: minimal fields + task state list
      - long: includes per-task details and traces (best-effort)
    """

    mode = (mode or "short").strip().lower()

    payload: Dict[str, Any] = {
        "ok": bool(st.ok),
        "connector_state": st.connector_state,
        "worker_id": st.worker_id,
        "task_states": list(st.task_states),
    }

    if mode == "short":
        return payload

    # long mode: include more structured info based on raw status
    raw = st.raw if isinstance(st.raw, dict) else {}

    conn_val = raw.get("connector")
    conn_raw: Dict[str, Any] = conn_val if isinstance(conn_val, dict) else {}

    tasks_val = raw.get("tasks")
    tasks_raw: List[Any] = tasks_val if isinstance(tasks_val, list) else []

    tasks: List[Dict[str, Any]] = []
    for t in tasks_raw:
        if not isinstance(t, dict):
            continue
        td: Dict[str, Any] = {
            "id": t.get("id"),
            "state": t.get("state"),
            "worker_id": t.get("worker_id"),
        }
        if str(t.get("state", "")).upper() == "FAILED":
            trace = t.get("trace")
            if trace:
                td["trace"] = trace
        tasks.append(td)

    payload["connector"] = {
        "state": conn_raw.get("state"),
        "worker_id": conn_raw.get("worker_id"),
        **({"trace": conn_raw.get("trace")} if conn_raw.get("trace") else {}),
    }
    payload["tasks"] = tasks

    if include_raw:
        payload["raw"] = st.raw

    return payload


def format_status_short_line(name: str, st: ConnectorStatus) -> str:
    return (
        f"{name}: connector={st.connector_state} tasks={list(st.task_states)} "
        f"worker={st.worker_id or '-'} ok={bool(st.ok)}"
    )


def format_status_long_text(
    name: str, st: ConnectorStatus, *, include_raw: bool = False
) -> str:
    parts: List[str] = []
    parts.append(f"Connector: {name}")
    parts.append(f"  connector_state: {st.connector_state}")
    if st.worker_id:
        parts.append(f"  worker_id: {st.worker_id}")
    parts.append(f"  ok: {bool(st.ok)}")
    parts.append("  tasks:")

    raw = st.raw if isinstance(st.raw, dict) else {}

    tasks_val = raw.get("tasks")
    tasks_raw: List[Any] | None = tasks_val if isinstance(tasks_val, list) else None

    if tasks_raw is None:
        # fallback to simple task state list
        for idx, t_state in enumerate(st.task_states):
            parts.append(f"    - id={idx} state={t_state}")
    else:
        for t in tasks_raw:
            if not isinstance(t, dict):
                continue
            tid = t.get("id")
            raw_state = t.get("state")
            wid = t.get("worker_id")
            parts.append(f"    - id={tid} state={raw_state} worker_id={wid}")
            if str(raw_state).upper() == "FAILED" and t.get("trace") is not None:
                trace = str(t.get("trace"))
                # keep full trace, but indent nicely
                for line in trace.splitlines()[:2000]:
                    parts.append(f"        {line}")

    conn_val = raw.get("connector")
    conn_raw = conn_val if isinstance(conn_val, dict) else None
    if (
        conn_raw
        and str(conn_raw.get("state", "")).upper() == "FAILED"
        and conn_raw.get("trace") is not None
    ):
        parts.append("  connector_trace:")
        trace = str(conn_raw.get("trace"))
        for line in trace.splitlines()[:2000]:
            parts.append(f"    {line}")

    if include_raw:
        parts.append("  raw:")
        parts.append(json.dumps(st.raw, ensure_ascii=False, indent=2, sort_keys=True))

    if not st.ok:
        suggestions = RunbookRouter.default().suggest(
            [
                name,
                st.connector_state,
                json.dumps(st.raw, ensure_ascii=False, sort_keys=True),
            ]
        )
        if suggestions:
            parts.append("  suggested_runbooks:")
            for item in suggestions[:5]:
                parts.append(f"    - {item.title}: {item.path}")

    return "\n".join(parts)
