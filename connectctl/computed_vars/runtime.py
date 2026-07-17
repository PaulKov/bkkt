from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..settings_models import Settings
from .api import ComputedVarContext
from .dependencies import ComputedVarDependencyGraph
from .evaluator import ComputedVarEvaluator
from .loader import RepoComputedVarLoader
from .models import ComputedVarDescriptor, ComputedVarGraph, ComputedVarValue
from .registry import ComputedVarRegistry


@dataclass(frozen=True)
class ComputedVarRuntime:
    """Facade used by render and CLI for repo-local computed variables."""

    registry: ComputedVarRegistry

    @classmethod
    def empty(cls) -> "ComputedVarRuntime":
        return cls(ComputedVarRegistry())

    @classmethod
    def from_settings(cls, settings: Settings) -> "ComputedVarRuntime":
        runtime = cls.empty()
        computed_cfg = settings.computed_vars
        if computed_cfg.enabled and computed_cfg.allow_repo_python:
            RepoComputedVarLoader(
                repo_root=settings.repo.root,
                paths=computed_cfg.paths,
            ).load_into(runtime.registry)
        return runtime

    @classmethod
    def from_repo(
        cls,
        repo_root: Path,
        *,
        paths: tuple[str, ...] = ("bkkt/computed_vars",),
    ) -> "ComputedVarRuntime":
        runtime = cls.empty()
        RepoComputedVarLoader(repo_root=repo_root, paths=paths).load_into(
            runtime.registry
        )
        return runtime

    def evaluate_all(
        self,
        context: Mapping[str, Any],
        *,
        computed_context: ComputedVarContext,
    ) -> tuple[ComputedVarValue, ...]:
        return ComputedVarEvaluator(self.registry).evaluate_all(
            context,
            computed_context=computed_context,
        )

    def evaluate_one(
        self,
        name: str,
        *,
        computed_context: ComputedVarContext,
    ) -> str | int | float | bool:
        self.registry.get(name)
        return (
            ComputedVarEvaluator(self.registry)
            .evaluate_target(
                name,
                computed_context.variables.values,
                computed_context=computed_context,
            )
            .value
        )

    def list_computed_vars(self) -> list[ComputedVarDescriptor]:
        return self.registry.list()

    def graph(self) -> ComputedVarGraph:
        return ComputedVarDependencyGraph(self.registry).to_graph()

    def impact(self, name: str) -> tuple[str, ...]:
        self.registry.get(name)
        return ComputedVarDependencyGraph(self.registry).impact(name)
