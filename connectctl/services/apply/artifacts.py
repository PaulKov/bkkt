from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, cast

from ...adapters.filesystem import LocalFileSystem
from ...exceptions import ConfigError, ValidationError
from ...models import ConnectorManifest
from ...ports import FileSystem
from ...repo import ConnectorRepo


@dataclass(frozen=True)
class RenderedArtifact:
    manifest: ConnectorManifest
    connectctl: dict[str, Any]


@dataclass(frozen=True)
class RenderedArtifactLoader:
    """Loader for rendered connector artifacts.

    Artifacts are produced by commands like `connectctl render-changed` and contain
    at minimum:

        {"name": "...", "config": {"k": "v", ...}}

    When artifact-based deploy is enabled (--from-rendered), ApplyService can load
    configs from this directory and avoid re-rendering manifests.

    DI:
    - чтение файлов делается через FileSystem порт (fs)
    """

    repo_root: Path
    repo: ConnectorRepo
    artifact_dir: Path
    render_index: Dict[str, Any]
    fs: FileSystem
    strict: bool = False

    @classmethod
    def from_args(
        cls,
        args: Any,
        *,
        repo_root: Path,
        repo: ConnectorRepo,
        fs: Optional[FileSystem] = None,
    ) -> Optional["RenderedArtifactLoader"]:
        raw = getattr(args, "from_rendered", None)
        if not raw:
            return None

        fs = fs or LocalFileSystem()

        artifact_dir = Path(str(raw))
        if not artifact_dir.is_absolute():
            artifact_dir = (repo_root / artifact_dir).resolve()

        idx_path = artifact_dir / "_index.json"
        render_index: Dict[str, Any] = {}
        if fs.exists(idx_path):
            try:
                render_index = json.loads(fs.read_text(idx_path, encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise ConfigError(f"Invalid JSON in {idx_path}: {e}") from e

        strict = bool(getattr(args, "artifact_strict", False))

        return cls(
            repo_root=repo_root,
            repo=repo,
            artifact_dir=artifact_dir,
            render_index=render_index,
            fs=fs,
            strict=strict,
        )

    def try_load(self, manifest_path: Path) -> Optional[RenderedArtifact]:
        """Try to load rendered manifest from artifacts.

        Returns None if artifact is missing. Does NOT enforce strict mode.
        """

        p = manifest_path

        artifact_name = self._guess_artifact_name(p)
        if artifact_name is None:
            return None

        ap = self.artifact_dir / artifact_name
        if not self.fs.exists(ap):
            return None

        data = json.loads(self.fs.read_text(ap, encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or not data.get("name")
            or not isinstance(data.get("config"), dict)
        ):
            raise ValidationError(
                f"Invalid rendered artifact: {ap} (expected keys: name, config)"
            )

        info = self.repo.parse_connector_path(p)
        manifest = ConnectorManifest(
            name=str(data["name"]),
            config={k: str(v) for k, v in data["config"].items()},
            source_path=p,
            info=info,
        )
        connectctl_val = data.get("connectctl")
        connectctl: Dict[str, Any] = (
            cast(Dict[str, Any], connectctl_val)
            if isinstance(connectctl_val, dict)
            else {}
        )
        return RenderedArtifact(manifest=manifest, connectctl=connectctl)

    def _guess_artifact_name(self, manifest_path: Path) -> Optional[str]:
        """Best-effort artifact name inference.

        1) Prefer _index.json mapping by relpath.
        2) Fallback: read minimal env manifest and use <name>.json.
        """

        p = manifest_path

        # Prefer the index mapping by relpath.
        try:
            rel = str(p.resolve().relative_to(self.repo_root))
        except Exception:
            rel = str(p)
        rel = rel.replace(os.sep, "/")

        entry = self.render_index.get(rel)
        artifact_name: Optional[str] = None
        if isinstance(entry, dict):
            artifact_name = entry.get("file") or (
                f"{entry.get('name')}.json" if entry.get("name") else None
            )

        # Fallback: try <name>.json by reading minimal env manifest.
        if artifact_name is None:
            try:
                raw_obj = json.loads(self.fs.read_text(p, encoding="utf-8"))
                if isinstance(raw_obj, dict) and raw_obj.get("name"):
                    artifact_name = f"{raw_obj['name']}.json"
            except Exception:
                artifact_name = None

        return artifact_name


def write_rendered_artifact(
    rendered_dir: Path,
    manifest: ConnectorManifest,
    *,
    fs: Optional[FileSystem] = None,
) -> Path:
    """Write rendered {name,config} artifact to rendered_dir."""

    fs = fs or LocalFileSystem()
    fs.mkdirs(rendered_dir, exist_ok=True)

    out_path = rendered_dir / f"{manifest.name}.json"
    fs.write_text(
        out_path,
        json.dumps(
            {"name": manifest.name, "config": manifest.config},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return out_path


def write_rollback_artifact(
    rendered_dir: Path,
    manifest: ConnectorManifest,
    *,
    previous_config: Optional[Dict[str, Any]],
    desired_config: Dict[str, Any],
    error: BaseException,
    fs: Optional[FileSystem] = None,
) -> Path:
    """Write an operator-friendly rollback artifact after a failed deploy."""

    fs = fs or LocalFileSystem()
    out_dir = rendered_dir / "_rollback"
    fs.mkdirs(out_dir, exist_ok=True)
    out_path = out_dir / f"{manifest.name}.rollback.json"
    fs.write_text(
        out_path,
        json.dumps(
            {
                "name": manifest.name,
                "source_path": str(manifest.source_path),
                "previous_config": previous_config,
                "desired_config": desired_config,
                "error": str(error),
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return out_path
