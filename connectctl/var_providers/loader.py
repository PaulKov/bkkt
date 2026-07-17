from __future__ import annotations

import importlib.util
import inspect
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

from ..exceptions import ConnectCtlError
from .api import VAR_PROVIDER_ATTR, VarProviderSpec
from .models import VarProviderDescriptor
from .registry import VarProviderRegistry


class RepoVarProviderLoader:
    """Loads trusted Python variable providers from a manifests repository."""

    def __init__(self, *, repo_root: Path, paths: Sequence[str]) -> None:
        self.repo_root = repo_root.resolve()
        self.paths = tuple(paths)

    def load_into(self, registry: VarProviderRegistry) -> None:
        for file_path in self._iter_files():
            self._load_file(file_path, registry)

    def _iter_files(self) -> Iterable[Path]:
        for raw_path in self.paths:
            path = (self.repo_root / raw_path).resolve()
            if not self._is_inside_repo(path):
                raise ConnectCtlError(
                    f"Variable provider path escapes repo root: {raw_path!r}. "
                    "Keep var_providers.paths inside the manifests repository."
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

    def _load_file(self, path: Path, registry: VarProviderRegistry) -> None:
        module_name = f"_bkkt_repo_var_providers_{abs(hash(path))}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ConnectCtlError(f"Cannot load BKKT variable provider module: {path}")
        module = importlib.util.module_from_spec(spec)
        try:
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception as e:
            raise ConnectCtlError(
                f"Failed to import BKKT variable provider module {path}: {e}. "
                "Run `bkkt vars providers doctor` for details."
            ) from e

        for _attr_name, value in inspect.getmembers(module):
            provider_spec = getattr(value, VAR_PROVIDER_ATTR, None)
            if isinstance(provider_spec, VarProviderSpec):
                registry.register(
                    VarProviderDescriptor(
                        name=provider_spec.name,
                        fn=value,
                        description=provider_spec.description,
                        source_path=path,
                        provides=provider_spec.provides,
                        allow_shadow=provider_spec.allow_shadow,
                        capabilities=provider_spec.capabilities,
                        timeout_ms=provider_spec.timeout_ms,
                    )
                )

    def _is_inside_repo(self, path: Path) -> bool:
        try:
            path.relative_to(self.repo_root)
            return True
        except ValueError:
            return False
