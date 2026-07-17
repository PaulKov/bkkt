from __future__ import annotations

from pathlib import Path
from typing import Iterator, List, Optional

from ..models import Environment, RepoConfig
from ..ports import FileSystem
from .scanner_paths import find_base_file_for, parse_connector_path
from .scanner_regex import is_base_filename, is_deployable_connector_filename


class ConnectorRepo:
    def __init__(self, cfg: RepoConfig, fs: FileSystem | None = None):
        self.cfg = cfg
        self.fs = fs

    def iter_json_files(self) -> Iterator[Path]:
        root = self.cfg.connectors_root
        it = self.fs.glob(root, "**/*.json") if self.fs else root.rglob("*.json")
        for p in it:
            # Skip hidden and ignored dirs
            if any(part.startswith(".") for part in p.parts):
                continue
            if any(part in self.cfg.ignore_dirs for part in p.parts):
                continue
            yield p

    def iter_deployable_connector_files(
        self, env: Optional[Environment] = None
    ) -> Iterator[Path]:
        for p in self.iter_json_files():
            if self.is_deployable_connector_file(p):
                info = self.parse_connector_path(p)
                if env is None or info.env == env:
                    yield p

    def iter_deployable_manifests(
        self, env: Optional[Environment] = None
    ) -> Iterator[Path]:
        """Backward-compatible alias for iter_deployable_connector_files()."""
        yield from self.iter_deployable_connector_files(env=env)

    def list_env_manifests(self, env: Environment) -> List[Path]:
        """Convenience helper for CLI: list deployable manifests for one env."""
        return list(self.iter_deployable_connector_files(env=env))

    def is_deployable_connector_file(self, path: Path) -> bool:
        return is_deployable_connector_filename(path.name)

    def is_base_file(self, path: Path) -> bool:
        return is_base_filename(path.name)

    def parse_connector_path(self, path: Path, must_exist: bool = True):
        return parse_connector_path(self.cfg, path, must_exist=must_exist, fs=self.fs)

    def find_base_file_for(self, env_file: Path) -> Optional[Path]:
        return find_base_file_for(self.cfg, env_file, fs=self.fs)

    def list_domains(self) -> List[str]:
        # Domain dirs are immediate children under connectors_root excluding ignored.
        root = self.cfg.connectors_root
        domains = []
        it = self.fs.iterdir(root) if self.fs else root.iterdir()
        for child in it:
            if self.fs:
                if not self.fs.is_dir(child):
                    continue
            else:
                if not child.is_dir():
                    continue
            if child.name in self.cfg.ignore_dirs:
                continue
            if child.name.startswith("."):
                continue
            domains.append(child.name)
        return sorted(domains)
