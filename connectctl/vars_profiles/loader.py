from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from ..exceptions import ConnectCtlError
from .models import VarsProfile


class VarsProfileLoader:
    """Loads named runtime variable profiles from `bkkt/vars/profiles`."""

    DEFAULT_DIR = Path("bkkt/vars/profiles")

    def __init__(self, repo_root: Path, *, profiles_dir: str | None = None) -> None:
        self.repo_root = repo_root.resolve()
        self.profiles_dir = Path(profiles_dir) if profiles_dir else self.DEFAULT_DIR

    def list(self) -> tuple[VarsProfile, ...]:
        return tuple(self._load_file(path) for path in self._iter_files())

    def get(self, name: str) -> VarsProfile:
        wanted = name.strip()
        if not wanted:
            raise ConnectCtlError("vars profile name must not be empty")
        for profile in self.list():
            if profile.name == wanted:
                return profile
        available = ", ".join(profile.name for profile in self.list()) or "(none)"
        raise ConnectCtlError(
            f"Vars profile {wanted!r} not found. Available profiles: {available}"
        )

    def _iter_files(self) -> Iterable[Path]:
        root = (self.repo_root / self.profiles_dir).resolve()
        try:
            root.relative_to(self.repo_root)
        except ValueError as e:
            raise ConnectCtlError(
                "vars profiles directory must stay inside repo root"
            ) from e
        if not root.exists():
            return
        for path in sorted(root.glob("*.yml")) + sorted(root.glob("*.yaml")):
            if path.name.startswith("_"):
                continue
            yield path

    def _load_file(self, path: Path) -> VarsProfile:
        try:
            path.resolve().relative_to(self.repo_root)
        except ValueError as e:
            raise ConnectCtlError(f"vars profile file escapes repo root: {path}") from e
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ConnectCtlError(f"{path}: vars profile must be a YAML mapping")
        values = raw.get("vars", {}) or {}
        if not isinstance(values, dict):
            raise ConnectCtlError(f"{path}: vars profile `vars` must be a mapping")
        name = str(raw.get("name") or path.stem).strip()
        if not name:
            raise ConnectCtlError(f"{path}: vars profile name must not be empty")
        return VarsProfile(
            name=name,
            description=str(raw.get("description", "") or ""),
            values=dict(values),
            source_path=path,
        )
