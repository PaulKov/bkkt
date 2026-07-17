from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Iterable, Sequence

from ..exceptions import ConnectCtlError
from .api import COMPUTED_VAR_ATTR, ComputedVarSpec
from .models import ComputedVarDescriptor
from .registry import ComputedVarRegistry


class RepoComputedVarLoader:
    """Loads trusted Python computed variables from a manifests repository."""

    def __init__(self, *, repo_root: Path, paths: Sequence[str]) -> None:
        self.repo_root = repo_root.resolve()
        self.paths = tuple(paths)

    def load_into(self, registry: ComputedVarRegistry) -> None:
        for file_path in self._iter_files():
            self._load_file(file_path, registry)

    def _iter_files(self) -> Iterable[Path]:
        for raw_path in self.paths:
            path = (self.repo_root / raw_path).resolve()
            if not self._is_inside_repo(path):
                raise ConnectCtlError(
                    f"Computed vars path escapes repo root: {raw_path!r}. "
                    "Keep computed_vars.paths inside the manifests repository."
                )
            if not path.exists():
                continue
            if path.is_file() and path.suffix == ".py":
                yield path
                continue
            if path.is_dir():
                for item in sorted(path.rglob("*.py")):
                    if item.name.startswith("_") or "__pycache__" in item.parts:
                        continue
                    yield item

    def _load_file(self, path: Path, registry: ComputedVarRegistry) -> None:
        module_name = f"_bkkt_repo_computed_vars_{abs(hash(path))}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ConnectCtlError(f"Cannot load BKKT computed var module: {path}")
        module = importlib.util.module_from_spec(spec)
        try:
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception as e:
            raise ConnectCtlError(
                f"Failed to import BKKT computed var module {path}: {e}. "
                "Run `bkkt vars computed doctor` for details."
            ) from e

        for _attr_name, value in inspect.getmembers(module):
            var_spec = getattr(value, COMPUTED_VAR_ATTR, None)
            if isinstance(var_spec, ComputedVarSpec):
                registry.register(
                    ComputedVarDescriptor(
                        name=var_spec.name,
                        fn=value,
                        description=var_spec.description,
                        source="repo",
                        source_path=path,
                        allow_shadow=var_spec.allow_shadow,
                        dependencies=var_spec.dependencies,
                        capabilities=var_spec.capabilities,
                    )
                )

    def _is_inside_repo(self, path: Path) -> bool:
        try:
            path.relative_to(self.repo_root)
            return True
        except ValueError:
            return False
