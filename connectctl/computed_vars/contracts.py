from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

from ..exceptions import ConnectCtlError
from .api import ComputedVarContext
from .models import (
    ComputedVarContractCase,
    ComputedVarContractResult,
    ComputedVarContractSuite,
)
from .runtime import ComputedVarRuntime


ContextFactory = Callable[[str | None], ComputedVarContext]


class ComputedVarContractLoader:
    """Discovers YAML computed-var contract tests in a manifests repository."""

    DEFAULT_GLOB = "bkkt/computed_vars/tests/**/*.yaml"

    def __init__(self, repo_root: Path, *, pattern: str | None = None) -> None:
        self.repo_root = repo_root.resolve()
        self.pattern = pattern or self.DEFAULT_GLOB

    def load(self) -> tuple[ComputedVarContractCase, ...]:
        return tuple(
            case for path in self._iter_files() for case in self._load_file(path)
        )

    def _iter_files(self) -> Iterable[Path]:
        yield from sorted(self.repo_root.glob(self.pattern))

    def _load_file(self, path: Path) -> list[ComputedVarContractCase]:
        try:
            path.resolve().relative_to(self.repo_root)
        except ValueError as e:
            raise ConnectCtlError(
                f"Computed var test file escapes repo root: {path}"
            ) from e
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ConnectCtlError(f"{path}: computed var test file must be a mapping")
        cases = raw.get("cases", []) or []
        if not isinstance(cases, list):
            raise ConnectCtlError(f"{path}: `cases` must be a list")
        return [
            _case_from_mapping(item, path=path, index=i) for i, item in enumerate(cases)
        ]


class ComputedVarContractRunner:
    """Runs computed-var contract cases against ComputedVarRuntime."""

    def __init__(
        self,
        runtime: ComputedVarRuntime,
        *,
        context_factory: ContextFactory,
    ) -> None:
        self.runtime = runtime
        self.context_factory = context_factory

    def run(
        self, cases: tuple[ComputedVarContractCase, ...]
    ) -> ComputedVarContractSuite:
        return ComputedVarContractSuite(tuple(self._run_one(case) for case in cases))

    def _run_one(self, case: ComputedVarContractCase) -> ComputedVarContractResult:
        try:
            actual = self.runtime.evaluate_one(
                case.variable,
                computed_context=self.context_factory(case.manifest),
            )
            if str(actual) == str(case.expect):
                return ComputedVarContractResult(
                    case=case,
                    status="passed",
                    actual=str(actual),
                )
            return ComputedVarContractResult(
                case=case,
                status="failed",
                actual=str(actual),
            )
        except Exception as e:
            return ComputedVarContractResult(case=case, status="failed", error=str(e))


def _case_from_mapping(item: Any, *, path: Path, index: int) -> ComputedVarContractCase:
    if not isinstance(item, dict):
        raise ConnectCtlError(f"{path}: cases[{index}] must be a mapping")
    variable = str(item.get("variable", "")).strip()
    if not variable:
        raise ConnectCtlError(f"{path}: cases[{index}].variable is required")
    return ComputedVarContractCase(
        name=str(item.get("name") or f"{variable} case {index + 1}"),
        variable=variable,
        expect=item.get("expect"),
        manifest=str(item["manifest"]) if item.get("manifest") is not None else None,
        source_path=path,
    )
