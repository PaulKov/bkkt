from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ..exceptions import ConnectApiError
from ..models import ConnectorManifest, ConnectorStatus
from .client_base import _TRANSIENT_STATUS_CODES
from .client_base import ConnectClientBase


class ConnectConnectorsMixin(ConnectClientBase):
    """Миксин с CRUD-операциями над коннекторами."""

    def list_connectors(self) -> Sequence[str]:
        attempts = []
        lists_by_endpoint: dict[str, list[str]] = {}

        for base in self._candidate_bases():
            resp, attempt = self._request_to_base(base, "GET", "/connectors")
            attempts.append(attempt)
            if resp is None:
                self._mark_unhealthy(attempt)
                continue
            if resp.status_code in _TRANSIENT_STATUS_CODES:
                self._mark_unhealthy(attempt)
                continue
            if resp.status_code != 200:
                raise ConnectApiError(
                    f"GET /connectors failed: HTTP {resp.status_code}: {resp.text}"
                )
            data = resp.json()
            if not isinstance(data, list):
                raise ConnectApiError(
                    f"GET /connectors returned unexpected payload from {base}: {data!r}"
                )
            lists_by_endpoint[base] = sorted(str(x) for x in data)

        if not lists_by_endpoint:
            raise self._all_failed_error("GET", "/connectors", attempts)
        self._connector_names_by_base = {
            base: tuple(names) for base, names in lists_by_endpoint.items()
        }

        unique_lists = {tuple(v) for v in lists_by_endpoint.values()}
        if len(unique_lists) > 1:
            counts = ", ".join(
                f"{base}={len(names)}" for base, names in lists_by_endpoint.items()
            )
            self._log.warning(
                "Kafka Connect endpoints returned inconsistent /connectors lists; using union (%s)",
                counts,
            )

        union: set[str] = set()
        for names in lists_by_endpoint.values():
            union.update(names)
        return sorted(union)

    def get_config_optional(
        self, name: str, *, preferred_base: str | None = None
    ) -> Optional[Dict[str, Any]]:
        """Return connector config or None if the connector does not exist."""

        resp = self._request_connector_get(
            f"/connectors/{name}/config", preferred_base=preferred_base
        )
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            return None
        raise ConnectApiError(
            f"GET /connectors/{name}/config failed: HTTP {resp.status_code}: {resp.text}"
        )

    def get_config_optional_fast(self, name: str) -> Optional[Dict[str, Any]]:
        """Return connector config using status worker_id as a /config endpoint hint.

        Some Kafka Connect workers can answer `/status` and `/connectors` quickly
        while timing out on `/config`. Connector status includes the worker that
        currently owns the connector task; preferring that endpoint avoids broad
        live discovery stampedes on stale or partially unhealthy control-plane
        workers.
        """

        preferred_base: str | None = None
        if len(self.base_urls) > 1:
            try:
                status = self.get_status(name)
                preferred_base = self._base_for_worker_id(status.worker_id)
            except Exception as exc:
                self._log.debug("Worker hint lookup failed for %s: %s", name, exc)
        return self.get_config_optional(name, preferred_base=preferred_base)

    def prime_config_endpoint(
        self,
        names: Sequence[str],
        *,
        probe_timeout: Tuple[float, float] = (1.0, 3.0),
    ) -> Optional[str]:
        """Select one responsive `/config` endpoint for bulk live discovery."""

        if len(self.base_urls) <= 1 or self._get_preferred_config_base():
            return self._get_preferred_config_base()

        samples = [str(name).strip() for name in names if str(name).strip()]
        if not samples:
            return None

        sample = samples[0]
        path = f"/connectors/{sample}/config"
        for base in self._config_probe_bases():
            resp, attempt = self._request_to_base(
                base,
                "GET",
                path,
                timeout=probe_timeout,
            )
            if resp is None or attempt.transient:
                self._mark_unhealthy(attempt)
                continue
            self._mark_config_healthy(base)
            self._set_preferred_config_base(base)
            return base
        return None

    def _config_probe_bases(self) -> list[str]:
        order = {base: idx for idx, base in enumerate(self.base_urls)}
        return sorted(
            self._candidate_bases(),
            key=lambda base: (
                -len(self._connector_names_by_base.get(base, ())),
                order.get(base, 0),
            ),
        )

    def get_status(self, name: str) -> ConnectorStatus:
        resp = self._request_connector_get(f"/connectors/{name}/status")
        if resp.status_code != 200:
            raise ConnectApiError(
                f"GET /connectors/{name}/status failed: HTTP {resp.status_code}: {resp.text}"
            )
        data = resp.json()
        connector_state = data.get("connector", {}).get("state", "UNKNOWN")
        worker_id = data.get("connector", {}).get("worker_id")
        tasks = data.get("tasks", []) or []
        task_states = tuple(t.get("state", "UNKNOWN") for t in tasks)
        return ConnectorStatus(
            name=name,
            connector_state=str(connector_state),
            worker_id=str(worker_id) if worker_id else None,
            task_states=task_states,
            raw=data,
        )

    def get_config(
        self, name: str, *, preferred_base: str | None = None
    ) -> Dict[str, Any]:
        resp = self._request_connector_get(
            f"/connectors/{name}/config", preferred_base=preferred_base
        )
        if resp.status_code != 200:
            raise ConnectApiError(
                f"GET /connectors/{name}/config failed: HTTP {resp.status_code}: {resp.text}"
            )
        return resp.json()

    def upsert(self, manifest: ConnectorManifest) -> None:
        """Create or update a connector config in an idempotent way."""

        payload = manifest.to_connect_upsert_payload()

        # PUT /connectors/{name}/config is the preferred idempotent endpoint.
        resp = self._request_connector_put_config(manifest.name, payload)
        if resp.status_code in {200, 201}:
            return

        # Fallback for older Connect setups where PUT might not create new connector:
        if resp.status_code == 404:
            create_payload = {"name": manifest.name, "config": payload}
            resp2 = self._request(
                "POST",
                "/connectors",
                headers={"Content-Type": "application/json"},
                data=json.dumps(create_payload),
            )
            if resp2.status_code in {200, 201}:
                return
            raise ConnectApiError(
                f"POST /connectors failed: HTTP {resp2.status_code}: {resp2.text}"
            )

        raise ConnectApiError(
            f"PUT /connectors/{manifest.name}/config failed: HTTP {resp.status_code}: {resp.text}"
        )

    def delete(self, name: str) -> None:
        resp = self._request("DELETE", f"/connectors/{name}")
        if resp.status_code in {200, 202, 204}:
            return
        # Idempotency: deleting a non-existing connector is ok.
        if resp.status_code == 404:
            return
        raise ConnectApiError(
            f"DELETE /connectors/{name} failed: HTTP {resp.status_code}: {resp.text}"
        )

    def create_connector(self, name: str, config: Mapping[str, Any]) -> None:
        """Create a connector from a raw config map.

        Kafka Connect REST API:
          POST /connectors  {"name": "...", "config": {...}}

        This is NOT idempotent: if the connector already exists, Connect typically returns 409.
        BKKT verifies connector existence after ambiguous endpoint timeouts before
        retrying on another worker.
        """
        cfg = dict(config)
        payload = {"name": name, "config": cfg}
        attempts = []

        for base in self._candidate_bases():
            resp, attempt = self._request_to_base(
                base,
                "POST",
                "/connectors",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
            )
            attempts.append(attempt)
            if resp is None or attempt.transient:
                self._mark_unhealthy(attempt)
                try:
                    current = self.get_config_optional(name)
                    if current == cfg:
                        self._log.info(
                            "POST /connectors was already applied; verified connector via healthy endpoint"
                        )
                        return
                except Exception as e:
                    self._log.debug(
                        "Connector verification after ambiguous POST failed: %s", e
                    )
                continue
            if resp.status_code in {200, 201}:
                return
            raise ConnectApiError(
                f"POST /connectors failed: HTTP {resp.status_code}: {resp.text}"
            )

        raise self._all_failed_error("POST", "/connectors", attempts)

    def update_connector(self, name: str, config: Mapping[str, Any]) -> None:
        """Update an existing connector using raw config map.

        Kafka Connect REST API:
          PUT /connectors/<name>/config  {...}

        This is idempotent (for the same config). Most Connect deployments return 404 if missing.
        """
        resp = self._request_connector_put_config(name, dict(config))
        if resp.status_code in {200, 201}:
            return
        raise ConnectApiError(
            f"PUT /connectors/{name}/config failed: HTTP {resp.status_code}: {resp.text}"
        )

    def get_offsets(self, name: str) -> Dict[str, Any]:
        resp = self._request_connector_get(f"/connectors/{name}/offsets")
        if resp.status_code != 200:
            raise ConnectApiError(
                f"GET /connectors/{name}/offsets failed: HTTP {resp.status_code}: {resp.text}"
            )
        data = resp.json()
        if not isinstance(data, dict):
            raise ConnectApiError(
                f"GET /connectors/{name}/offsets returned unexpected payload: {data!r}"
            )
        return data

    def patch_offsets(self, name: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        resp = self._request(
            "PATCH",
            f"/connectors/{name}/offsets",
            headers={"Content-Type": "application/json"},
            data=json.dumps(dict(payload)),
        )
        if resp.status_code in {200, 202, 204}:
            if resp.text:
                try:
                    data = resp.json()
                    return data if isinstance(data, dict) else {"response": data}
                except Exception:
                    return {"response": resp.text}
            return {}
        raise ConnectApiError(
            f"PATCH /connectors/{name}/offsets failed: HTTP {resp.status_code}: {resp.text}"
        )
