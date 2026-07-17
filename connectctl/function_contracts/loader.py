from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml

from ..exceptions import ConnectCtlError
from .models import FunctionContractCase


class FunctionContractLoader:
    """Discovers YAML function contract tests in a manifests repository."""

    DEFAULT_GLOB = "bkkt/functions/tests/**/*.yaml"

    def __init__(self, repo_root: Path, *, pattern: str | None = None) -> None:
        self.repo_root = repo_root.resolve()
        self.pattern = pattern or self.DEFAULT_GLOB

    def load(self) -> tuple[FunctionContractCase, ...]:
        return tuple(
            case for path in self._iter_files() for case in self._load_file(path)
        )

    def _iter_files(self) -> Iterable[Path]:
        yield from sorted(self.repo_root.glob(self.pattern))

    def _load_file(self, path: Path) -> list[FunctionContractCase]:
        try:
            path.resolve().relative_to(self.repo_root)
        except ValueError as e:
            raise ConnectCtlError(
                f"Function test file escapes repo root: {path}"
            ) from e
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ConnectCtlError(f"{path}: function test file must be a mapping")
        cases = raw.get("cases", []) or []
        if not isinstance(cases, list):
            raise ConnectCtlError(f"{path}: `cases` must be a list")
        return [
            _case_from_mapping(item, path=path, index=i) for i, item in enumerate(cases)
        ]


def _case_from_mapping(item: Any, *, path: Path, index: int) -> FunctionContractCase:
    if not isinstance(item, dict):
        raise ConnectCtlError(f"{path}: cases[{index}] must be a mapping")
    function = str(item.get("function", "")).strip()
    if not function:
        raise ConnectCtlError(f"{path}: cases[{index}].function is required")
    raw_args = item.get("args", []) or []
    if not isinstance(raw_args, list):
        raise ConnectCtlError(f"{path}: cases[{index}].args must be a list")
    raw_kwargs = item.get("kwargs", {}) or {}
    if not isinstance(raw_kwargs, dict):
        raise ConnectCtlError(f"{path}: cases[{index}].kwargs must be a mapping")
    return FunctionContractCase(
        name=str(item.get("name") or f"{function} case {index + 1}"),
        function=function,
        args=tuple(raw_args),
        kwargs=dict(raw_kwargs),
        expect=item.get("expect"),
        manifest=str(item["manifest"]) if item.get("manifest") is not None else None,
        source_path=path,
    )
