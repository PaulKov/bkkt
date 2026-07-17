from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from ..exceptions import ConnectCtlError
from .models import RuntimeSafetyConfig


T = TypeVar("T")


class RuntimeSafetyPolicy:
    """Capability and soft-timeout policy for trusted repo-local callables."""

    def __init__(self, config: RuntimeSafetyConfig | None = None) -> None:
        self.config = config or RuntimeSafetyConfig()

    def run_callable(
        self,
        *,
        kind: str,
        name: str,
        capabilities: tuple[str, ...] = (),
        timeout_ms: int | None = None,
        call: Callable[[], T],
    ) -> T:
        self.check_capabilities(kind=kind, name=name, capabilities=capabilities)
        started = time.perf_counter()
        result = call()
        elapsed_ms = (time.perf_counter() - started) * 1000
        budget_ms = timeout_ms if timeout_ms is not None else self.config.max_call_ms
        if budget_ms is not None and elapsed_ms > budget_ms:
            raise ConnectCtlError(
                "runtime_timeout: "
                f"{kind} {name!r} took {elapsed_ms:.2f}ms, "
                f"budget is {budget_ms}ms. Increase max_call_ms only after "
                "reviewing render determinism and CI impact."
            )
        return result

    def check_capabilities(
        self, *, kind: str, name: str, capabilities: tuple[str, ...]
    ) -> None:
        allowed = tuple(item.strip() for item in self.config.allowed_capabilities)
        if not allowed or "*" in allowed:
            return
        denied = tuple(item for item in capabilities if item and item not in allowed)
        if denied:
            raise ConnectCtlError(
                "runtime_capability_denied: "
                f"{kind} {name!r} requires capabilities {list(denied)}, "
                f"allowed capabilities are {list(allowed)}."
            )
