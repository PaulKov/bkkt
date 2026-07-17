from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Iterable, Sequence

from ..exceptions import ConnectCtlError
from .api import PLUGIN_ATTR, FunctionSpec
from .models import FunctionDescriptor
from .registry import FunctionRegistry


class RepoFunctionLoader:
    """Loads trusted Python functions from a manifests repository."""

    def __init__(self, *, repo_root: Path, paths: Sequence[str]) -> None:
        self.repo_root = repo_root.resolve()
        self.paths = tuple(paths)

    def load_into(self, registry: FunctionRegistry) -> None:
        for file_path in self._iter_function_files():
            self._load_file(file_path, registry)

    def _iter_function_files(self) -> Iterable[Path]:
        for raw_path in self.paths:
            path = (self.repo_root / raw_path).resolve()
            if not self._is_inside_repo(path):
                raise ConnectCtlError(
                    f"Function path escapes repo root: {raw_path!r}. "
                    "Keep functions.paths inside the manifests repository."
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

    def _load_file(self, path: Path, registry: FunctionRegistry) -> None:
        module_name = f"_bkkt_repo_functions_{abs(hash(path))}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ConnectCtlError(f"Cannot load BKKT function module: {path}")
        module = importlib.util.module_from_spec(spec)
        try:
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception as e:
            raise ConnectCtlError(
                f"Failed to import BKKT function module {path}: {e}. "
                "Run `bkkt functions doctor` for details."
            ) from e

        for _attr_name, value in inspect.getmembers(module):
            fn_spec = getattr(value, PLUGIN_ATTR, None)
            if isinstance(fn_spec, FunctionSpec):
                registry.register(
                    FunctionDescriptor(
                        name=fn_spec.name,
                        fn=value,
                        description=fn_spec.description,
                        source="repo",
                        source_path=path,
                        deprecated_since=fn_spec.deprecated_since,
                        remove_after=fn_spec.remove_after,
                        replacement=fn_spec.replacement,
                        capabilities=fn_spec.capabilities,
                        timeout_ms=fn_spec.timeout_ms,
                    )
                )

    def _is_inside_repo(self, path: Path) -> bool:
        try:
            path.relative_to(self.repo_root)
            return True
        except ValueError:
            return False
