import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Tuple

import pytest

from connectctl.connect import ConnectClient
from connectctl.models import (
    ConnectorManifest,
    ConnectorPathInfo,
    ConnectorType,
    Environment,
)


@dataclass
class FakeConnectState:
    configs: Dict[str, Dict]
    offsets: Dict[str, Dict] | None = None
    counts: Dict[str, int] | None = None
    delay_after_put_config_s: float = 0.0
    delay_get_config_s: float = 0.0
    worker_id: str | None = None

    def count(self, key: str) -> None:
        if self.counts is None:
            self.counts = {}
        self.counts[key] = self.counts.get(key, 0) + 1


def _make_handler(state: FakeConnectState):
    class Handler(BaseHTTPRequestHandler):
        # Silence default stderr logging in tests.
        def log_message(self, format, *args):  # noqa: A002
            return

        def _send_json(self, code: int, obj) -> None:
            data = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except BrokenPipeError:
                return

        def _read_json(self) -> Dict:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            return json.loads(raw or "{}")

        def do_GET(self):  # noqa: N802
            state.count(f"GET {self.path}")
            if self.path == "/connectors":
                return self._send_json(200, sorted(state.configs.keys()))

            if self.path.startswith("/connectors/") and self.path.endswith("/config"):
                if state.delay_get_config_s > 0:
                    time.sleep(state.delay_get_config_s)
                name = self.path.split("/", 3)[2]
                if name not in state.configs:
                    return self._send_json(404, {"error": "not found"})
                return self._send_json(200, state.configs[name])

            if self.path.startswith("/connectors/") and self.path.endswith("/status"):
                name = self.path.split("/", 3)[2]
                if name not in state.configs:
                    return self._send_json(404, {"error": "not found"})
                tasks_max = int(state.configs[name].get("tasks.max", "1") or "1")

                # Testing hook: allow overriding connector/task state via special config keys.
                # These keys are ignored by real Kafka Connect, but help us simulate failures.
                connector_state = str(
                    state.configs[name].get("__test_connector_state", "RUNNING")
                )
                task_state = str(
                    state.configs[name].get("__test_task_state", "RUNNING")
                )
                return self._send_json(
                    200,
                    {
                        "name": name,
                        "connector": {
                            "state": connector_state,
                            "worker_id": state.worker_id or "fake:8083",
                        },
                        "tasks": [
                            {"id": i, "state": task_state} for i in range(tasks_max)
                        ],
                    },
                )

            if self.path.startswith("/connectors/") and self.path.endswith("/offsets"):
                name = self.path.split("/", 3)[2]
                offsets = state.offsets or {}
                if name not in state.configs and name not in offsets:
                    return self._send_json(404, {"error": "not found"})
                return self._send_json(200, offsets.get(name, {"offsets": []}))

            return self._send_json(404, {"error": "unknown path", "path": self.path})

        def do_PUT(self):  # noqa: N802
            state.count(f"PUT {self.path}")
            if self.path.startswith("/connector-plugins/") and self.path.endswith(
                "/config/validate"
            ):
                # Minimal fake of Kafka Connect config validation endpoint.
                # We treat presence of '__test_force_validation_error' as a validation failure.
                cfg = self._read_json()
                has_error = bool(cfg.get("__test_force_validation_error"))
                errs = ["forced validation error"] if has_error else []
                return self._send_json(
                    200,
                    {
                        "name": "fake",
                        "error_count": 1 if has_error else 0,
                        "configs": (
                            [
                                {
                                    "definition": {
                                        "name": "__test_force_validation_error"
                                    },
                                    "errors": errs,
                                }
                            ]
                            if has_error
                            else []
                        ),
                    },
                )

            if self.path.startswith("/connectors/") and self.path.endswith("/config"):
                name = self.path.split("/", 3)[2]
                cfg = self._read_json()
                existed = name in state.configs
                state.configs[name] = cfg
                if state.delay_after_put_config_s > 0:
                    time.sleep(state.delay_after_put_config_s)
                return self._send_json(200 if existed else 201, cfg)
            return self._send_json(404, {"error": "unknown path", "path": self.path})

        def do_POST(self):  # noqa: N802
            state.count(f"POST {self.path}")
            if self.path.startswith("/connector-plugins/") and self.path.endswith(
                "/config/validate"
            ):
                # Minimal fake of Kafka Connect config validation endpoint.
                # We treat presence of '__test_force_validation_error' as a validation failure.
                cfg = self._read_json()
                has_error = bool(cfg.get("__test_force_validation_error"))
                errs = ["forced validation error"] if has_error else []
                return self._send_json(
                    200,
                    {
                        "name": "fake",
                        "error_count": 1 if has_error else 0,
                        "configs": (
                            [
                                {
                                    "definition": {
                                        "name": "__test_force_validation_error"
                                    },
                                    "errors": errs,
                                }
                            ]
                            if has_error
                            else []
                        ),
                    },
                )

            if self.path == "/connectors":
                payload = self._read_json()
                name = payload.get("name")
                cfg = payload.get("config") or {}
                if not name:
                    return self._send_json(400, {"error": "missing name"})
                state.configs[name] = cfg
                return self._send_json(201, {"name": name})
            return self._send_json(404, {"error": "unknown path", "path": self.path})

        def do_PATCH(self):  # noqa: N802
            state.count(f"PATCH {self.path}")
            if self.path.startswith("/connectors/") and self.path.endswith("/offsets"):
                name = self.path.split("/", 3)[2]
                if state.offsets is None:
                    state.offsets = {}
                state.offsets[name] = self._read_json()
                return self._send_json(200, {"updated": True})
            return self._send_json(404, {"error": "unknown path", "path": self.path})

        def do_DELETE(self):  # noqa: N802
            if self.path.startswith("/connectors/"):
                name = self.path.split("/", 3)[2]
                if name in state.configs:
                    del state.configs[name]
                    self.send_response(204)
                    self.end_headers()
                    return
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(404)
            self.end_headers()

    return Handler


@pytest.fixture
def fake_connect() -> Tuple[str, FakeConnectState]:
    state = FakeConnectState(configs={})
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address
    url = f"http://{host}:{port}"

    try:
        yield url, state
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _start_fake_server(
    state: FakeConnectState,
) -> tuple[str, ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return f"http://{host}:{port}", server, thread


def _mk_manifest(name: str) -> ConnectorManifest:
    info = ConnectorPathInfo(
        path=Path("/tmp/x.json"),
        relpath=Path("x.json"),
        domain="acme",
        connector_type=ConnectorType.source,
        system="postgres",
        connector_dir="connector_acme__configuration",
        env=Environment.stage,
        remainder="source_acme__configuration__common_tables",
        mode=None,
    )
    return ConnectorManifest(
        name=name,
        config={"connector.class": "X", "tasks.max": "2"},
        source_path=Path("/tmp/x.json"),
        info=info,
    )


@pytest.mark.integration
def test_connect_client_upsert_status_delete(fake_connect):
    url, state = fake_connect

    client = ConnectClient(
        ["http://127.0.0.1:1", url]
    )  # first host will fail, second succeeds
    manifest = _mk_manifest("stage.acme.configuration.source.postgres.0")

    client.upsert(manifest)
    assert manifest.name in state.configs

    cfg = client.get_config(manifest.name)
    assert cfg["connector.class"] == "X"

    st = client.wait_for_healthy(
        manifest.name, initial_delay_s=0, timeout_s=2, poll_interval_s=0.1
    )
    assert st.ok
    assert st.task_states == ("RUNNING", "RUNNING")

    client.delete(manifest.name)
    assert manifest.name not in state.configs


@pytest.mark.integration
def test_wait_for_healthy_raises_on_timeout(fake_connect):
    url, state = fake_connect

    client = ConnectClient([url])
    manifest = _mk_manifest("stage.acme.configuration.source.postgres.1")

    # Inject a failure state using testing hook keys.
    manifest_fail = ConnectorManifest(
        name=manifest.name,
        config={
            **manifest.config,
            "__test_connector_state": "FAILED",
            "__test_task_state": "FAILED",
        },
        source_path=manifest.source_path,
        info=manifest.info,
    )

    client.upsert(manifest_fail)

    from connectctl.exceptions import ConnectApiError

    with pytest.raises(ConnectApiError):
        client.wait_for_healthy(
            manifest_fail.name, initial_delay_s=0, timeout_s=0.5, poll_interval_s=0.1
        )


@pytest.mark.integration
def test_plugin_config_validate_endpoint(fake_connect):
    url, _state = fake_connect

    client = ConnectClient([url])
    manifest = _mk_manifest("stage.acme.configuration.source.postgres.2")

    # 1) Successful validation (no error_count)
    res = client.validate_config("X", manifest.config)
    assert int(res.get("error_count") or 0) == 0

    # 2) Failure should surface as ValidationError from validate_manifest()
    from connectctl.exceptions import ValidationError

    bad = ConnectorManifest(
        name=manifest.name,
        config={**manifest.config, "__test_force_validation_error": "1"},
        source_path=manifest.source_path,
        info=manifest.info,
    )

    with pytest.raises(ValidationError):
        client.validate_manifest(bad)


@pytest.mark.integration
def test_connector_specific_get_treats_404_as_stale_until_all_endpoints_agree():
    missing_state = FakeConnectState(configs={})
    live_state = FakeConnectState(
        configs={"prod.demo.orders.sink.raw.iceberg.0": {"connector.class": "X"}}
    )
    url_missing, srv_missing, th_missing = _start_fake_server(missing_state)
    url_live, srv_live, th_live = _start_fake_server(live_state)

    try:
        client = ConnectClient([url_missing, url_live])

        cfg = client.get_config_optional("prod.demo.orders.sink.raw.iceberg.0")
        assert cfg == {"connector.class": "X"}

        st = client.get_status("prod.demo.orders.sink.raw.iceberg.0")
        assert st.ok
    finally:
        srv_missing.shutdown()
        srv_live.shutdown()
        th_missing.join(timeout=2)
        th_live.join(timeout=2)


@pytest.mark.integration
def test_list_connectors_uses_union_when_worker_lists_disagree():
    state_a = FakeConnectState(configs={"a.connector.0": {"connector.class": "X"}})
    state_b = FakeConnectState(configs={"b.connector.0": {"connector.class": "X"}})
    url_a, srv_a, th_a = _start_fake_server(state_a)
    url_b, srv_b, th_b = _start_fake_server(state_b)

    try:
        client = ConnectClient([url_a, url_b])
        assert client.list_connectors() == ["a.connector.0", "b.connector.0"]
    finally:
        srv_a.shutdown()
        srv_b.shutdown()
        th_a.join(timeout=2)
        th_b.join(timeout=2)


@pytest.mark.integration
def test_unhealthy_endpoint_is_cached_after_timeout():
    slow_state = FakeConnectState(configs={}, delay_get_config_s=0.5)
    live_state = FakeConnectState(
        configs={"prod.demo.orders.sink.raw.iceberg.0": {"connector.class": "X"}}
    )
    url_slow, srv_slow, th_slow = _start_fake_server(slow_state)
    url_live, srv_live, th_live = _start_fake_server(live_state)

    try:
        client = ConnectClient([url_slow, url_live], timeout=(0.1, 0.1))
        assert client.get_config_optional("prod.demo.orders.sink.raw.iceberg.0")
        assert client.get_config_optional("prod.demo.orders.sink.raw.iceberg.0")
        assert slow_state.counts
        assert (
            slow_state.counts.get(
                "GET /connectors/prod.demo.orders.sink.raw.iceberg.0/config"
            )
            == 1
        )
    finally:
        srv_slow.shutdown()
        srv_live.shutdown()
        th_slow.join(timeout=2)
        th_live.join(timeout=2)


@pytest.mark.integration
def test_parallel_config_reads_do_not_stampede_unhealthy_endpoint():
    configs = {
        f"prod.demo.orders.sink.raw.iceberg.{idx}": {"connector.class": "X"}
        for idx in range(8)
    }
    slow_state = FakeConnectState(configs=configs, delay_get_config_s=0.5)
    live_state = FakeConnectState(configs=configs)
    url_slow, srv_slow, th_slow = _start_fake_server(slow_state)
    url_live, srv_live, th_live = _start_fake_server(live_state)

    try:
        client = ConnectClient([url_slow, url_live], timeout=(0.1, 0.1))
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(client.get_config_optional, sorted(configs)))

        assert all(result == {"connector.class": "X"} for result in results)
        assert slow_state.counts
        slow_config_calls = sum(
            count
            for path, count in slow_state.counts.items()
            if path.endswith("/config")
        )
        assert slow_config_calls == 1
    finally:
        srv_slow.shutdown()
        srv_live.shutdown()
        th_slow.join(timeout=2)
        th_live.join(timeout=2)


@pytest.mark.integration
def test_fast_config_read_prefers_status_worker_endpoint():
    name = "prod.demo.orders.sink.raw.iceberg.0"
    cfg = {"connector.class": "X"}
    slow_state = FakeConnectState(configs={name: cfg}, delay_get_config_s=0.5)
    live_state = FakeConnectState(configs={name: cfg})
    url_slow, srv_slow, th_slow = _start_fake_server(slow_state)
    url_live, srv_live, th_live = _start_fake_server(live_state)
    live_worker_id = url_live.removeprefix("http://")
    slow_state.worker_id = live_worker_id
    live_state.worker_id = live_worker_id

    try:
        client = ConnectClient([url_slow, url_live], timeout=(0.1, 0.1))
        assert client.get_config_optional_fast(name) == cfg
        assert slow_state.counts
        assert slow_state.counts.get(f"GET /connectors/{name}/status") == 1
        assert slow_state.counts.get(f"GET /connectors/{name}/config") is None
        assert live_state.counts
        assert live_state.counts.get(f"GET /connectors/{name}/config") == 1
    finally:
        srv_slow.shutdown()
        srv_live.shutdown()
        th_slow.join(timeout=2)
        th_live.join(timeout=2)


@pytest.mark.integration
def test_prime_config_endpoint_uses_short_probe_and_reuses_healthy_base():
    name = "prod.demo.orders.sink.raw.iceberg.0"
    cfg = {"connector.class": "X"}
    slow_state = FakeConnectState(configs={name: cfg}, delay_get_config_s=0.5)
    live_state = FakeConnectState(configs={name: cfg})
    url_slow, srv_slow, th_slow = _start_fake_server(slow_state)
    url_live, srv_live, th_live = _start_fake_server(live_state)

    try:
        client = ConnectClient([url_slow, url_live], timeout=(0.1, 0.1))
        assert (
            client.prime_config_endpoint([name], probe_timeout=(0.1, 0.1)) == url_live
        )
        assert client.get_config_optional(name) == cfg
        assert slow_state.counts
        assert slow_state.counts.get(f"GET /connectors/{name}/config") == 1
        assert live_state.counts
        assert live_state.counts.get(f"GET /connectors/{name}/config") == 2
    finally:
        srv_slow.shutdown()
        srv_live.shutdown()
        th_slow.join(timeout=2)
        th_live.join(timeout=2)


@pytest.mark.integration
def test_prime_config_endpoint_prefers_endpoint_with_larger_connector_list():
    name = "prod.demo.orders.sink.raw.iceberg.0"
    extra_name = "prod.demo.orders.sink.raw.iceberg.1"
    cfg = {"connector.class": "X"}
    slow_state = FakeConnectState(configs={name: cfg}, delay_get_config_s=0.5)
    live_state = FakeConnectState(configs={name: cfg, extra_name: cfg})
    url_slow, srv_slow, th_slow = _start_fake_server(slow_state)
    url_live, srv_live, th_live = _start_fake_server(live_state)

    try:
        client = ConnectClient([url_slow, url_live], timeout=(0.1, 0.1))
        assert client.list_connectors() == [name, extra_name]
        assert (
            client.prime_config_endpoint([name], probe_timeout=(0.1, 0.1)) == url_live
        )
        assert slow_state.counts
        assert slow_state.counts.get(f"GET /connectors/{name}/config") is None
    finally:
        srv_slow.shutdown()
        srv_live.shutdown()
        th_slow.join(timeout=2)
        th_live.join(timeout=2)


@pytest.mark.integration
def test_endpoint_diagnostics_use_bounded_config_timeout():
    name = "prod.demo.orders.sink.raw.iceberg.0"
    cfg = {"connector.class": "X"}
    slow_state = FakeConnectState(configs={name: cfg}, delay_get_config_s=0.5)
    url_slow, srv_slow, th_slow = _start_fake_server(slow_state)

    try:
        client = ConnectClient([url_slow], timeout=(0.1, 0.1))
        diagnostics = client.list_endpoint_diagnostics(
            name=name, config_timeout=(0.1, 0.1)
        )
        config_attempt = next(
            attempt
            for attempt in diagnostics[0].checks
            if attempt.path == f"/connectors/{name}/config"
        )
        assert config_attempt.error
        assert config_attempt.elapsed_ms < 400
    finally:
        srv_slow.shutdown()
        th_slow.join(timeout=2)


@pytest.mark.integration
def test_ambiguous_put_timeout_is_verified_before_retrying():
    name = "prod.demo.orders.sink.raw.iceberg.0"
    shared = FakeConnectState(
        configs={name: {"connector.class": "Old"}},
        delay_after_put_config_s=0.5,
    )
    url_slow, srv_slow, th_slow = _start_fake_server(shared)
    # Same state simulates another worker that can observe the config after the
    # first worker applied it but timed out before responding.
    url_reader, srv_reader, th_reader = _start_fake_server(shared)

    try:
        client = ConnectClient([url_slow, url_reader], timeout=(0.1, 0.1))
        desired = {"connector.class": "New"}
        client.update_connector(name, desired)

        assert shared.configs[name] == desired
        assert shared.counts
        assert shared.counts.get(f"PUT /connectors/{name}/config") == 1
    finally:
        srv_slow.shutdown()
        srv_reader.shutdown()
        th_slow.join(timeout=2)
        th_reader.join(timeout=2)


@pytest.mark.integration
def test_offsets_get_and_patch(fake_connect):
    url, state = fake_connect
    name = "stage.acme.configuration.source.postgres.0"
    state.configs[name] = {"connector.class": "X"}
    state.offsets = {name: {"offsets": [{"partition": {"server": "old"}}]}}

    client = ConnectClient([url])
    assert client.get_offsets(name)["offsets"][0]["partition"]["server"] == "old"

    payload = {"offsets": [{"partition": {"server": "new"}, "offset": {"pos": 1}}]}
    result = client.patch_offsets(name, payload)
    assert result == {"updated": True}
    assert state.offsets[name] == payload
