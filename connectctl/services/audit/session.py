from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import TracebackType
from typing import Any, Literal

from ..state.store import StateStore


_SENSITIVE_FRAGMENTS = ("password", "token", "secret", "credential")


class AuditSession:
    """Small command-scoped audit writer.

    Command modules should only say *what* happened. Persistence details stay in
    StateStore, and sensitive argv material is redacted before writing.
    """

    def __init__(
        self,
        *,
        command: str,
        args: Namespace,
        store: StateStore | None,
        plan_hash: str | None = None,
    ) -> None:
        self._command = command
        self._args = args
        self._store = store
        self._plan_hash = plan_hash
        self._run_id: str | None = None
        self._result_code: int | None = None
        self.disabled = store is None

    def __enter__(self) -> "AuditSession":
        if self._store is None:
            return self
        run = self._store.create_run(
            command=self._command,
            env=_arg_value(self._args, "env"),
            cluster=_arg_value(self._args, "cluster")
            or _arg_value(self._args, "clusters"),
            args_summary=_args_summary(self._args),
            plan_hash=self._plan_hash,
        )
        self._run_id = run.id
        self.event("command_started")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        if self._store is None or self._run_id is None:
            return False
        if exc is None:
            outcome = "success" if self._result_code in (None, 0) else "failed"
            error = (
                None
                if outcome == "success"
                else f"command returned exit code {self._result_code}"
            )
            self.event(
                "command_finished",
                level="INFO" if outcome == "success" else "ERROR",
                payload={"result_code": self._result_code},
            )
            self._store.finish_run(self._run_id, outcome=outcome, error=error)
            return False
        self.event("command_failed", level="ERROR", message=str(exc))
        self._store.finish_run(self._run_id, outcome="failed", error=str(exc))
        return False

    def set_result_code(self, result_code: int) -> None:
        self._result_code = int(result_code)

    def event(
        self,
        event_type: str,
        *,
        level: str = "INFO",
        message: str = "",
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self._store is None or self._run_id is None:
            return
        self._store.append_event(
            self._run_id,
            event_type=event_type,
            level=level,
            message=message,
            payload=payload or {},
        )


def _arg_value(args: Namespace, name: str) -> str | None:
    value = getattr(args, name, None)
    if value is None:
        return None
    return str(value)


def _args_summary(args: Namespace) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, value in sorted(vars(args).items()):
        if key in {"func", "_command"} or key.startswith("_"):
            continue
        summary[key] = (
            "***REDACTED***" if _is_sensitive(key) else _json_safe_value(value)
        )
    return summary


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in _SENSITIVE_FRAGMENTS)


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe_value(item) for item in value]
    return str(value)
