from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..exceptions import ConnectCtlError
from .models import FunctionLockDocument, LockedFunction, LockedPackage


LOCKFILE_VERSION = 1
DEFAULT_LOCKFILE = Path("bkkt/functions.lock.yaml")


class FunctionLockfile:
    """YAML IO for `bkkt/functions.lock.yaml`."""

    def __init__(self, repo_root: Path, *, path: Path | None = None) -> None:
        self.repo_root = repo_root.resolve()
        self.path = self.resolve_path(path)

    def resolve_path(self, path: Path | None = None) -> Path:
        raw = path or DEFAULT_LOCKFILE
        resolved = raw if raw.is_absolute() else self.repo_root / raw
        try:
            resolved.resolve().relative_to(self.repo_root)
        except ValueError as e:
            raise ConnectCtlError(
                f"Function lockfile path escapes repo root: {raw}"
            ) from e
        return resolved

    def load(self) -> FunctionLockDocument:
        if not self.path.exists():
            raise ConnectCtlError(
                f"Function lockfile not found: {self._display(self.path)}. "
                "Run `bkkt functions package lock --write` first."
            )
        raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ConnectCtlError(f"{self._display(self.path)} must be a YAML mapping")
        version = int(raw.get("version") or 0)
        if version != LOCKFILE_VERSION:
            raise ConnectCtlError(
                f"{self._display(self.path)} has unsupported version {version}; "
                f"expected {LOCKFILE_VERSION}."
            )
        packages_raw = raw.get("packages", []) or []
        if not isinstance(packages_raw, list):
            raise ConnectCtlError(
                f"{self._display(self.path)} `packages` must be a list"
            )
        packages = tuple(self._load_package(item) for item in packages_raw)
        return FunctionLockDocument(version=version, packages=tuple(sorted(packages)))

    def write(self, document: FunctionLockDocument) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                document.to_payload(),
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            ),
            encoding="utf-8",
        )
        return self.path

    def _load_package(self, raw: Any) -> LockedPackage:
        if not isinstance(raw, dict):
            raise ConnectCtlError("Function lock package entry must be a mapping")
        name = str(raw.get("name") or "").strip()
        if not name:
            raise ConnectCtlError("Function lock package name must not be empty")
        functions_raw = raw.get("functions", []) or []
        if not isinstance(functions_raw, list):
            raise ConnectCtlError(
                f"Function lock package {name!r} functions must be a list"
            )
        functions = tuple(self._load_function(name, item) for item in functions_raw)
        return LockedPackage(name=name, functions=tuple(sorted(functions)))

    @staticmethod
    def _load_function(package: str, raw: Any) -> LockedFunction:
        if not isinstance(raw, dict):
            raise ConnectCtlError("Function lock function entry must be a mapping")
        name = str(raw.get("name") or "").strip()
        fingerprint = str(raw.get("fingerprint") or "").strip()
        if not name:
            raise ConnectCtlError("Function lock function name must not be empty")
        if not fingerprint.startswith("sha256:"):
            raise ConnectCtlError(
                f"Function lock entry {name!r} has invalid fingerprint"
            )
        capabilities_raw = raw.get("capabilities", []) or []
        lifecycle_raw = raw.get("lifecycle", {}) or {}
        if not isinstance(capabilities_raw, list):
            raise ConnectCtlError(
                f"Function lock entry {name!r} capabilities must be a list"
            )
        if not isinstance(lifecycle_raw, dict):
            raise ConnectCtlError(
                f"Function lock entry {name!r} lifecycle must be a mapping"
            )
        source_path = raw.get("source_path")
        return LockedFunction(
            name=name,
            package=str(raw.get("package") or package),
            source=str(raw.get("source") or ""),
            source_path=str(source_path) if source_path is not None else None,
            fingerprint=fingerprint,
            description=str(raw.get("description") or ""),
            capabilities=tuple(str(item) for item in capabilities_raw),
            lifecycle=dict(lifecycle_raw),
        )

    def _display(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.repo_root).as_posix()
        except ValueError:
            return str(path)
