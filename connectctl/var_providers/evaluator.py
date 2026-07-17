from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any

from ..exceptions import ConnectCtlError
from ..runtime_safety import RuntimeSafetyPolicy
from .api import VarProviderContext
from .models import VarProviderDescriptor, VarProviderRunResult, VarProviderValue


class VarProviderEvaluator:
    """Executes repo-local variable providers against a read-only context."""

    def __init__(self, safety: RuntimeSafetyPolicy | None = None) -> None:
        self.safety = safety or RuntimeSafetyPolicy()

    def evaluate_one(
        self,
        descriptor: VarProviderDescriptor,
        context: Mapping[str, Any],
        *,
        provider_context: VarProviderContext,
    ) -> VarProviderRunResult:
        def call() -> Any:
            kwargs: dict[str, Any] = {}
            if "ctx" in inspect.signature(descriptor.fn).parameters:
                kwargs["ctx"] = provider_context
            return descriptor.fn(**kwargs)

        try:
            raw = self.safety.run_callable(
                kind="variable provider",
                name=descriptor.name,
                capabilities=descriptor.capabilities,
                timeout_ms=descriptor.timeout_ms,
                call=call,
            )
        except Exception as e:
            if isinstance(e, ConnectCtlError):
                raise
            raise ConnectCtlError(
                f"Variable provider {descriptor.name!r} failed: {e}"
            ) from e
        if not isinstance(raw, Mapping):
            raise ConnectCtlError(
                "provider_return_type_mismatch: "
                f"Variable provider {descriptor.name!r} must return a mapping, "
                f"got {type(raw).__name__}."
            )

        values: list[VarProviderValue] = []
        for raw_key, raw_value in raw.items():
            key = str(raw_key).strip()
            if not key:
                raise ConnectCtlError(
                    f"provider_key_empty: Variable provider {descriptor.name!r} "
                    "returned an empty key."
                )
            if key in context and not descriptor.allow_shadow:
                raise ConnectCtlError(
                    "provider_shadowed_variable: "
                    f"Variable provider {descriptor.name!r} returned {key!r}, "
                    "but that variable already exists. Rename the provider key or "
                    "set allow_shadow=True explicitly."
                )
            if not isinstance(raw_value, (str, int, float, bool)):
                raise ConnectCtlError(
                    "provider_value_type_mismatch: "
                    f"Variable provider {descriptor.name!r} value {key!r} must be "
                    f"scalar str/int/float/bool, got {type(raw_value).__name__}."
                )
            values.append(
                VarProviderValue(
                    key=key,
                    value=raw_value,
                    source=f"provider:{descriptor.name}",
                )
            )
        return VarProviderRunResult(
            provider=descriptor,
            values=tuple(sorted(values, key=lambda item: item.key)),
        )
