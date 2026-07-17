from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any, Optional, Sequence, Tuple
from urllib.parse import urlparse

import requests

from ..exceptions import ConnectApiError
from ..logging_utils import get_logger

_DEFAULT_TIMEOUT = (5.0, 30.0)  # connect, read
_TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class EndpointAttempt:
    """Single Kafka Connect endpoint attempt.

    The object is intentionally serializable-friendly: commands can reuse it for
    endpoint diagnostics and exceptions can render a compact matrix.
    """

    base_url: str
    method: str
    path: str
    status_code: int | None
    elapsed_ms: float
    error: str | None = None
    response_preview: str | None = None

    @property
    def transient(self) -> bool:
        if self.error:
            return True
        return self.status_code in _TRANSIENT_STATUS_CODES

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "base_url": self.base_url,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "transient": self.transient,
        }
        if self.error:
            payload["error"] = self.error
        if self.response_preview:
            payload["response_preview"] = self.response_preview
        return payload


@dataclass(frozen=True)
class EndpointDiagnostic:
    base_url: str
    checks: tuple[EndpointAttempt, ...]

    @property
    def healthy(self) -> bool:
        return any(a.status_code is not None and not a.transient for a in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "healthy": self.healthy,
            "checks": [a.to_dict() for a in self.checks],
        }


class ConnectClientBase:
    """Базовый HTTP-клиент Kafka Connect с failover по нескольким base_url."""

    def __init__(
        self,
        base_urls: Sequence[str],
        timeout: Tuple[float, float] = _DEFAULT_TIMEOUT,
        session: Optional[requests.Session] = None,
        throttle=None,
        logger=None,
    ):
        if not base_urls:
            raise ValueError("base_urls must not be empty")
        self.base_urls: Sequence[str] = list(base_urls)
        self.timeout = timeout
        # Requests Session is not guaranteed to be thread-safe.
        # Для параллельных bulk-операций используем thread-local Session,
        # сохраняя возможность DI через явный `session=`.
        self._shared_session = session
        self._local = threading.local()
        # Optional request throttle (rate limiter). DI-friendly.
        self._throttle = throttle
        self._log = get_logger(logger)
        self._unhealthy_bases: dict[str, str] = {}
        self._unhealthy_lock = threading.RLock()
        self._endpoint_attempt_locks: dict[str, threading.Lock] = {}
        self._config_healthy_bases: set[str] = set()
        self._preferred_config_base: str | None = None
        self._connector_names_by_base: dict[str, tuple[str, ...]] = {}

    def _get_session(self) -> requests.Session:
        if self._shared_session is not None:
            return self._shared_session

        sess = getattr(self._local, "session", None)
        if sess is None:
            sess = requests.Session()
            setattr(self._local, "session", sess)
        return sess

    def _request_to_base(
        self, base: str, method: str, path: str, **kwargs: Any
    ) -> tuple[requests.Response | None, EndpointAttempt]:
        if method.upper() == "GET" and _is_connector_config_path(path):
            return self._request_config_to_base(base, method, path, **kwargs)
        return self._perform_request_to_base(base, method, path, **kwargs)

    def _request_config_to_base(
        self, base: str, method: str, path: str, **kwargs: Any
    ) -> tuple[requests.Response | None, EndpointAttempt]:
        if self._is_config_healthy(base):
            return self._perform_request_to_base(base, method, path, **kwargs)

        lock = self._attempt_lock_for_base(base)
        with lock:
            if self._is_unhealthy(base):
                return (
                    None,
                    EndpointAttempt(
                        base_url=base,
                        method=method,
                        path=path,
                        status_code=None,
                        elapsed_ms=0.0,
                        error="SkippedUnhealthyEndpoint: endpoint already marked unhealthy",
                    ),
                )
            resp, attempt = self._perform_request_to_base(base, method, path, **kwargs)
            if resp is None or attempt.transient:
                self._mark_unhealthy(attempt)
            else:
                self._mark_config_healthy(base)
            return resp, attempt

    def _perform_request_to_base(
        self, base: str, method: str, path: str, **kwargs: Any
    ) -> tuple[requests.Response | None, EndpointAttempt]:
        url = base.rstrip("/") + "/" + path.lstrip("/")
        request_timeout = kwargs.pop("timeout", self.timeout)
        started = time.monotonic()
        self._log.debug("HTTP %s %s via %s", method, path, base)
        try:
            if self._throttle is not None:
                # Throttle each HTTP attempt to protect the cluster.
                # Works for all higher-level client methods as they call _request().
                self._throttle.acquire()
            resp = self._get_session().request(
                method, url, timeout=request_timeout, **kwargs
            )
        except requests.RequestException as e:
            elapsed_ms = (time.monotonic() - started) * 1000
            err = f"{type(e).__name__}: {e}"
            self._log.debug("HTTP %s %s via %s failed: %s", method, path, base, e)
            return (
                None,
                EndpointAttempt(
                    base_url=base,
                    method=method,
                    path=path,
                    status_code=None,
                    elapsed_ms=elapsed_ms,
                    error=err,
                ),
            )

        elapsed_ms = (time.monotonic() - started) * 1000
        preview = None
        if resp.status_code >= 400:
            preview = str(resp.text or "")[:500]
        return (
            resp,
            EndpointAttempt(
                base_url=base,
                method=method,
                path=path,
                status_code=resp.status_code,
                elapsed_ms=elapsed_ms,
                response_preview=preview,
            ),
        )

    def _attempt_lock_for_base(self, base: str) -> threading.Lock:
        with self._unhealthy_lock:
            lock = self._endpoint_attempt_locks.get(base)
            if lock is None:
                lock = threading.Lock()
                self._endpoint_attempt_locks[base] = lock
            return lock

    def _is_unhealthy(self, base: str) -> bool:
        with self._unhealthy_lock:
            return base in self._unhealthy_bases

    def _is_config_healthy(self, base: str) -> bool:
        with self._unhealthy_lock:
            return base in self._config_healthy_bases

    def _mark_config_healthy(self, base: str) -> None:
        with self._unhealthy_lock:
            self._config_healthy_bases.add(base)

    def _candidate_bases(self, *, preferred_base: str | None = None) -> list[str]:
        with self._unhealthy_lock:
            unhealthy = set(self._unhealthy_bases)
            if len(unhealthy) >= len(self.base_urls):
                # If every endpoint was marked unhealthy, try the full pool again:
                # the command may be long-running and a worker can recover while
                # we are active.
                self._unhealthy_bases.clear()
                unhealthy = set()

        ordered: list[str] = []
        if preferred_base and preferred_base in self.base_urls:
            ordered.append(preferred_base)
        ordered.extend(base for base in self.base_urls if base not in ordered)

        healthy = [base for base in ordered if base not in unhealthy]
        return healthy or ordered

    def _mark_unhealthy(self, attempt: EndpointAttempt) -> None:
        reason = attempt.error or f"HTTP {attempt.status_code}"
        with self._unhealthy_lock:
            first_seen = attempt.base_url not in self._unhealthy_bases
            self._unhealthy_bases[attempt.base_url] = reason
        if first_seen:
            self._log.warning(
                "Kafka Connect endpoint unhealthy: %s %s %s -> %s; trying another endpoint",
                attempt.base_url,
                attempt.method,
                attempt.path,
                reason,
            )

    def _format_attempt_matrix(self, attempts: Sequence[EndpointAttempt]) -> str:
        if not attempts:
            return "- no endpoint attempts recorded"
        lines = []
        for a in attempts:
            status = f"HTTP {a.status_code}" if a.status_code is not None else "ERROR"
            detail = a.error or a.response_preview or ""
            suffix = f": {detail}" if detail else ""
            lines.append(
                f"- {a.base_url} {a.method} {a.path}: {status} "
                f"({a.elapsed_ms:.1f} ms){suffix}"
            )
        return "\n".join(lines)

    def _all_failed_error(
        self, method: str, path: str, attempts: Sequence[EndpointAttempt]
    ) -> ConnectApiError:
        msg = (
            f"Kafka Connect request failed on all endpoints: {method} {path}\n"
            + self._format_attempt_matrix(attempts)
            + "\nHint: run `bkkt connect endpoints --env <env> --cluster <cluster>` "
            "to inspect worker REST health."
        )
        return ConnectApiError(msg)

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        attempts: list[EndpointAttempt] = []

        for base in self._candidate_bases():
            resp, attempt = self._request_to_base(base, method, path, **kwargs)
            attempts.append(attempt)
            if resp is None:
                self._mark_unhealthy(attempt)
                continue

            # Retry on transient gateway/worker issues.
            if resp.status_code in _TRANSIENT_STATUS_CODES:
                self._log.debug(
                    "HTTP %s %s via %s got %s (transient), trying next host",
                    method,
                    path,
                    base,
                    resp.status_code,
                )
                self._mark_unhealthy(attempt)
                continue

            return resp

        raise self._all_failed_error(method, path, attempts)

    def _request_connector_get(
        self, path: str, *, preferred_base: str | None = None
    ) -> requests.Response:
        """GET connector-specific resource with stale-worker tolerant 404 handling.

        Kafka Connect workers can temporarily disagree: one endpoint may return
        404 for `/connectors/<name>/status` while another already knows the
        connector. For connector-specific reads, 404 is final only after all
        reachable endpoints agree.
        """

        attempts: list[EndpointAttempt] = []
        not_found: requests.Response | None = None
        if preferred_base is None and _is_connector_config_path(path):
            preferred_base = self._get_preferred_config_base()

        for base in self._candidate_bases(preferred_base=preferred_base):
            resp, attempt = self._request_to_base(base, "GET", path)
            attempts.append(attempt)
            if resp is None:
                self._mark_unhealthy(attempt)
                continue
            if resp.status_code in _TRANSIENT_STATUS_CODES:
                self._mark_unhealthy(attempt)
                continue
            if resp.status_code == 404:
                not_found = resp
                continue
            return resp

        if not_found is not None:
            return not_found
        raise self._all_failed_error("GET", path, attempts)

    def _base_for_worker_id(self, worker_id: str | None) -> str | None:
        if not worker_id:
            return None
        worker_netloc = _extract_worker_netloc(worker_id)
        if not worker_netloc:
            return None
        for base in self.base_urls:
            if urlparse(base).netloc == worker_netloc:
                return base
        return None

    def _get_preferred_config_base(self) -> str | None:
        with self._unhealthy_lock:
            if (
                self._preferred_config_base
                and self._preferred_config_base not in self._unhealthy_bases
            ):
                return self._preferred_config_base
            return None

    def _set_preferred_config_base(self, base: str) -> None:
        with self._unhealthy_lock:
            if base not in self._unhealthy_bases:
                self._preferred_config_base = base

    def _request_connector_put_config(
        self, name: str, payload: dict[str, Any], **kwargs: Any
    ) -> requests.Response:
        """PUT connector config with timeout-safe verification before retry.

        PUT config is idempotent, but a worker can apply the config and timeout
        before returning. Before retrying on another endpoint, verify whether the
        desired config is already visible through the healthy pool.
        """

        import json

        attempts: list[EndpointAttempt] = []
        path = f"/connectors/{name}/config"
        not_found: requests.Response | None = None

        extra_headers = dict(kwargs.pop("headers", {}) or {})
        for base in self._candidate_bases():
            resp, attempt = self._request_to_base(
                base,
                "PUT",
                path,
                headers={"Content-Type": "application/json", **extra_headers},
                data=json.dumps(payload),
                **kwargs,
            )
            attempts.append(attempt)
            if resp is None or attempt.transient:
                self._mark_unhealthy(attempt)
                try:
                    current = self.get_config_optional(name)  # type: ignore[attr-defined]
                    if current == payload:
                        self._log.info(
                            "PUT %s was already applied; verified desired config via healthy endpoint",
                            path,
                        )

                        class _VerifiedResponse:
                            status_code = 200
                            text = "verified after ambiguous PUT"

                        return _VerifiedResponse()  # type: ignore[return-value]
                except Exception as e:
                    self._log.debug(
                        "Config verification after ambiguous PUT failed: %s", e
                    )
                continue
            if resp is not None and resp.status_code == 404:
                not_found = resp
                continue
            return resp

        if not_found is not None:
            return not_found
        raise self._all_failed_error("PUT", path, attempts)

    def list_endpoint_diagnostics(
        self,
        *,
        name: str | None = None,
        config_timeout: Tuple[float, float] = (1.0, 3.0),
    ) -> tuple[EndpointDiagnostic, ...]:
        paths = ["/", "/connectors", "/connector-plugins"]
        if name:
            paths.extend(
                [
                    f"/connectors/{name}/status",
                    f"/connectors/{name}/config",
                ]
            )

        diagnostics: list[EndpointDiagnostic] = []
        for base in self.base_urls:
            checks: list[EndpointAttempt] = []
            for path in paths:
                kwargs = (
                    {"timeout": config_timeout}
                    if _is_connector_config_path(path)
                    else {}
                )
                _resp, attempt = self._perform_request_to_base(
                    base, "GET", path, **kwargs
                )
                checks.append(attempt)
            diagnostics.append(EndpointDiagnostic(base_url=base, checks=tuple(checks)))
        return tuple(diagnostics)


def _extract_worker_netloc(worker_id: str) -> str | None:
    text = str(worker_id or "").strip()
    if not text:
        return None
    if "://" in text:
        return urlparse(text).netloc or None
    return text.split("/", 1)[0] or None


def _is_connector_config_path(path: str) -> bool:
    return path.startswith("/connectors/") and path.endswith("/config")
