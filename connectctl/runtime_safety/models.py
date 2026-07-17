from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeSafetyConfig:
    """Configurable guardrails for trusted repo-local Python execution.

    `max_call_ms` is a soft elapsed-time guard. It does not sandbox or kill
    Python code mid-flight; it fails the BKKT command if the callable returns
    after the configured budget.
    """

    max_call_ms: int | None = 5000
    allowed_capabilities: tuple[str, ...] = ()
