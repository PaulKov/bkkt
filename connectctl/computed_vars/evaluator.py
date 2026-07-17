from __future__ import annotations

import inspect
from typing import Any, Mapping

from ..exceptions import ConnectCtlError
from .api import ComputedVarContext
from .dependencies import ComputedVarDependencyGraph
from .models import ComputedVarDescriptor, ComputedVarValue
from .registry import ComputedVarRegistry


class ComputedVarEvaluator:
    """Evaluates computed variables against a read-only render context."""

    def __init__(self, registry: ComputedVarRegistry) -> None:
        self.registry = registry

    def evaluate_all(
        self,
        context: Mapping[str, Any],
        *,
        computed_context: ComputedVarContext,
    ) -> tuple[ComputedVarValue, ...]:
        order = ComputedVarDependencyGraph(self.registry).evaluation_order(
            context=context,
        )
        return self._evaluate_order(
            order,
            context=context,
            computed_context=computed_context,
        )

    def evaluate_target(
        self,
        name: str,
        context: Mapping[str, Any],
        *,
        computed_context: ComputedVarContext,
    ) -> ComputedVarValue:
        order = ComputedVarDependencyGraph(self.registry).evaluation_order(
            context=context,
            target=name,
        )
        values = self._evaluate_order(
            order,
            context=context,
            computed_context=computed_context,
        )
        return next(item for item in values if item.name == name)

    def _evaluate_order(
        self,
        order: tuple[ComputedVarDescriptor, ...],
        *,
        context: Mapping[str, Any],
        computed_context: ComputedVarContext,
    ) -> tuple[ComputedVarValue, ...]:
        values: list[ComputedVarValue] = []
        working_values = dict(context)
        working_sources = computed_context.variables.sources_dict()
        for descriptor in order:
            if descriptor.name in context and not descriptor.allow_shadow:
                raise ConnectCtlError(
                    f"Computed variable {descriptor.name!r} shadows existing variable. "
                    "Rename it or set allow_shadow=True explicitly."
                )
            step_context = ComputedVarContext.from_flat_context(
                working_values,
                sources=working_sources,
                repo_root=computed_context.repo_root,
                manifest_path=computed_context.manifest_path,
                metadata=computed_context.metadata,
            )
            value = self.evaluate_one(descriptor, step_context)
            working_values[descriptor.name] = value
            working_sources[descriptor.name] = f"computed:{descriptor.name}"
            values.append(
                ComputedVarValue(
                    name=descriptor.name,
                    value=value,
                    source=f"computed:{descriptor.name}",
                )
            )
        return tuple(values)

    def evaluate_one(
        self,
        descriptor: ComputedVarDescriptor,
        computed_context: ComputedVarContext,
    ) -> str | int | float | bool:
        kwargs: dict[str, Any] = {}
        sig = inspect.signature(descriptor.fn)
        if "ctx" in sig.parameters:
            kwargs["ctx"] = computed_context
        result = descriptor.fn(**kwargs)
        if not isinstance(result, (str, int, float, bool)):
            raise ConnectCtlError(
                f"Computed variable {descriptor.name!r} must return scalar "
                f"str/int/float/bool, got {type(result).__name__}."
            )
        return result
