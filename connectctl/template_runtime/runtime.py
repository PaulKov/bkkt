from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..runtime_safety import RuntimeSafetyPolicy
from ..settings_models import Settings
from ..utils.placeholders_models import PlaceholderTrace
from .api import FunctionContext
from .evaluator import FunctionEvaluator
from .loader import RepoFunctionLoader
from .models import FunctionDescriptor
from .registry import FunctionRegistry


@dataclass(frozen=True)
class TemplateRuntime:
    """Facade used by render/CLI to resolve functions consistently."""

    registry: FunctionRegistry
    safety: RuntimeSafetyPolicy = field(default_factory=RuntimeSafetyPolicy)

    @classmethod
    def builtins_only(cls) -> "TemplateRuntime":
        return cls(FunctionRegistry.with_builtins(), RuntimeSafetyPolicy())

    @classmethod
    def from_settings(cls, settings: Settings) -> "TemplateRuntime":
        functions_cfg = settings.functions
        runtime = cls(
            FunctionRegistry.with_builtins(),
            RuntimeSafetyPolicy(functions_cfg.runtime),
        )
        if functions_cfg.enabled and functions_cfg.allow_repo_python:
            RepoFunctionLoader(
                repo_root=settings.repo.root,
                paths=functions_cfg.paths,
            ).load_into(runtime.registry)
        return runtime

    @classmethod
    def from_repo(
        cls,
        repo_root: Path,
        *,
        paths: tuple[str, ...] = ("bkkt/functions",),
    ) -> "TemplateRuntime":
        runtime = cls.builtins_only()
        RepoFunctionLoader(repo_root=repo_root, paths=paths).load_into(runtime.registry)
        return runtime

    def evaluate(
        self,
        inner: str,
        context: Mapping[str, Any],
        *,
        trace: PlaceholderTrace | None = None,
        function_context: FunctionContext | None = None,
    ) -> str:
        return FunctionEvaluator(self.registry, self.safety).evaluate(
            inner,
            context,
            trace=trace,
            function_context=function_context,
        )

    def list_functions(self) -> list[FunctionDescriptor]:
        return self.registry.list()
