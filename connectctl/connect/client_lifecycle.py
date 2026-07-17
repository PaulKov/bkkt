from __future__ import annotations

import time
from typing import Dict, Optional

from ..exceptions import ConnectApiError
from ..models import ConnectorStatus
from .client_connectors import ConnectConnectorsMixin


class ConnectLifecycleMixin(ConnectConnectorsMixin):
    """Миксин с методами жизненного цикла коннекторов."""

    def restart(
        self,
        name: str,
        *,
        include_tasks: bool = True,
        only_failed: bool = False,
    ) -> None:
        """Restart a connector (and optionally its tasks).

        Kafka Connect REST API:
          POST /connectors/<name>/restart?includeTasks=true&onlyFailed=true

        Notes:
        - Not all Kafka Connect distributions support both query params; when unsupported,
          the endpoint typically returns 400/404. We surface that as ConnectApiError.
        """
        params: Dict[str, str] = {}
        if include_tasks:
            params["includeTasks"] = "true"
        if only_failed:
            params["onlyFailed"] = "true"

        resp = self._request(
            "POST", f"/connectors/{name}/restart", params=params if params else None
        )
        if resp.status_code in {200, 202, 204}:
            return
        raise ConnectApiError(
            f"POST /connectors/{name}/restart failed: HTTP {resp.status_code}: {resp.text}"
        )

    def restart_task(self, name: str, task_id: int) -> None:
        """Restart a single connector task.

        Kafka Connect REST API:
          POST /connectors/<name>/tasks/<task_id>/restart
        """
        resp = self._request("POST", f"/connectors/{name}/tasks/{int(task_id)}/restart")
        if resp.status_code in {200, 202, 204}:
            return
        raise ConnectApiError(
            f"POST /connectors/{name}/tasks/{int(task_id)}/restart failed: HTTP {resp.status_code}: {resp.text}"
        )

    def pause(self, name: str) -> None:
        """Pause a connector.

        Kafka Connect REST API:
          PUT /connectors/<name>/pause
        """

        resp = self._request("PUT", f"/connectors/{name}/pause")
        if resp.status_code in {200, 202, 204}:
            return
        raise ConnectApiError(
            f"PUT /connectors/{name}/pause failed: HTTP {resp.status_code}: {resp.text}"
        )

    def resume(self, name: str) -> None:
        """Resume a paused connector.

        Kafka Connect REST API:
          PUT /connectors/<name>/resume
        """

        resp = self._request("PUT", f"/connectors/{name}/resume")
        if resp.status_code in {200, 202, 204}:
            return
        raise ConnectApiError(
            f"PUT /connectors/{name}/resume failed: HTTP {resp.status_code}: {resp.text}"
        )

    def stop(self, name: str) -> None:
        """Stop a connector (если поддерживается вашим Kafka Connect).

        Kafka Connect REST API (зависит от версии):
          PUT /connectors/<name>/stop
        """

        resp = self._request("PUT", f"/connectors/{name}/stop")
        if resp.status_code in {200, 202, 204}:
            return
        raise ConnectApiError(
            f"PUT /connectors/{name}/stop failed: HTTP {resp.status_code}: {resp.text}"
        )

    def wait_for_healthy(
        self,
        name: str,
        *,
        initial_delay_s: float = 10,
        timeout_s: float = 300,
        poll_interval_s: float = 5,
    ) -> ConnectorStatus:
        """Wait until connector + all tasks are RUNNING.

        If the connector does not become healthy within `timeout_s`, this method
        raises :class:`~connectctl.exceptions.ConnectApiError` with the last known
        status included in the error message.
        """

        if initial_delay_s > 0:
            time.sleep(initial_delay_s)

        deadline = time.time() + timeout_s
        last_status: Optional[ConnectorStatus] = None

        while time.time() < deadline:
            st = self.get_status(name)
            last_status = st
            if st.ok:
                return st
            time.sleep(poll_interval_s)

        # Timeout: surface the last status as an exception so CI/CD fails loudly.
        if last_status is not None:
            # Try to include traces from /status when available (Connect often provides
            # a stacktrace for FAILED tasks).
            traces = []
            try:
                tasks = last_status.raw.get("tasks", []) or []
                for t in tasks:
                    trace = t.get("trace")
                    if trace:
                        first = str(trace).splitlines()[0][:200]
                        traces.append(first)
            except Exception:
                traces = []

            trace_msg = ""
            if traces:
                preview = "; ".join(traces[:3])
                more = f" (+{len(traces) - 3} more)" if len(traces) > 3 else ""
                trace_msg = f"; traces: {preview}{more}"
            raise ConnectApiError(
                f"Connector {name} did not become RUNNING within {timeout_s}s. "
                f"Last status: connector={last_status.connector_state} tasks={list(last_status.task_states)}"
                f"{trace_msg}"
            )

        raise ConnectApiError(f"Unable to fetch status for {name} within {timeout_s}s")
