from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..runtime_safety import RuntimeSafetyPolicy
from ..settings_models import Settings
from .api import VarProviderContext
from .evaluator import VarProviderEvaluator
from .loader import RepoVarProviderLoader
from .models import VarProviderDescriptor, VarProviderRunResult
from .registry import VarProviderRegistry


@dataclass(frozen=True)
class VarProviderRuntime:
    """Facade used by render and CLI for repo-local variable providers."""

    registry: VarProviderRegistry
    safety: RuntimeSafetyPolicy

    @classmethod
    def empty(cls) -> "VarProviderRuntime":
        return cls(VarProviderRegistry(), RuntimeSafetyPolicy())

    @classmethod
    def from_settings(cls, settings: Settings) -> "VarProviderRuntime":
        runtime = cls(
            VarProviderRegistry(),
            RuntimeSafetyPolicy(settings.var_providers.runtime),
        )
        providers_cfg = settings.var_providers
        if providers_cfg.enabled and providers_cfg.allow_repo_python:
            RepoVarProviderLoader(
                repo_root=settings.repo.root,
                paths=providers_cfg.paths,
            ).load_into(runtime.registry)
        return runtime

    @classmethod
    def from_repo(
        cls,
        repo_root: Path,
        *,
        paths: tuple[str, ...] = ("bkkt/var_providers",),
    ) -> "VarProviderRuntime":
        runtime = cls.empty()
        RepoVarProviderLoader(repo_root=repo_root, paths=paths).load_into(
            runtime.registry
        )
        return runtime

    def evaluate_all(
        self,
        context: Mapping[str, Any],
        *,
        provider_context: VarProviderContext,
    ) -> tuple[VarProviderRunResult, ...]:
        evaluator = VarProviderEvaluator(self.safety)
        working_context = dict(context)
        results: list[VarProviderRunResult] = []
        for descriptor in self.registry.list():
            result = evaluator.evaluate_one(
                descriptor,
                working_context,
                provider_context=provider_context,
            )
            for value in result.values:
                working_context[value.key] = value.value
            results.append(result)
        return tuple(results)

    def evaluate_one(
        self,
        name: str,
        context: Mapping[str, Any],
        *,
        provider_context: VarProviderContext,
    ) -> VarProviderRunResult:
        return VarProviderEvaluator(self.safety).evaluate_one(
            self.registry.get(name),
            context,
            provider_context=provider_context,
        )

    def list_providers(self) -> list[VarProviderDescriptor]:
        return self.registry.list()
