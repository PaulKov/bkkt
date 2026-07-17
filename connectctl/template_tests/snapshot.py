from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..exceptions import ConnectCtlError
from ..rendering.factory import build_renderer
from ..settings_models import Settings
from .models import TemplateSnapshot, TemplateSnapshotPlan


class TemplateSnapshotService:
    """Renders deterministic golden snapshots through the production renderer."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repo_root = settings.repo.root.resolve()
        self.renderer = build_renderer(settings)

    def render(self, manifest_path: str | Path) -> TemplateSnapshotPlan:
        path = _manifest_path(self.repo_root, manifest_path)
        result = self.renderer.render(path)
        snapshot = TemplateSnapshot(
            manifest=_relative(self.repo_root, path),
            name=result.manifest.name,
            config=dict(sorted(result.manifest.config.items())),
        )
        return TemplateSnapshotPlan(snapshot=snapshot)

    def write(
        self,
        plan: TemplateSnapshotPlan,
        output_file: str | Path,
        *,
        overwrite: bool = False,
    ) -> TemplateSnapshotPlan:
        target = _output_path(self.repo_root, output_file)
        if target.exists() and not overwrite:
            raise ConnectCtlError(
                f"Template snapshot already exists: {target}. Use --overwrite to replace it."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.safe_dump(
                {
                    "version": 1,
                    "snapshots": [plan.snapshot.to_payload()],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return TemplateSnapshotPlan(
            snapshot=plan.snapshot,
            status="written",
            output_file=_relative(self.repo_root, target),
        )


def load_snapshot_file(
    repo_root: Path, path: str | Path
) -> tuple[TemplateSnapshot, ...]:
    resolved = _output_path(repo_root, path)
    _assert_inside_repo(repo_root.resolve(), resolved)
    raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConnectCtlError(f"{resolved}: template snapshot file must be a mapping")
    snapshots_raw = raw.get("snapshots", []) or []
    if not isinstance(snapshots_raw, list):
        raise ConnectCtlError(f"{resolved}: `snapshots` must be a list")
    return tuple(
        _snapshot_from_mapping(item, path=resolved, index=index)
        for index, item in enumerate(snapshots_raw)
    )


def _snapshot_from_mapping(item: Any, *, path: Path, index: int) -> TemplateSnapshot:
    if not isinstance(item, dict):
        raise ConnectCtlError(f"{path}: snapshots[{index}] must be a mapping")
    manifest = str(item.get("manifest", "") or "").strip()
    name = str(item.get("name", "") or "").strip()
    config = item.get("config", {}) or {}
    if not manifest:
        raise ConnectCtlError(f"{path}: snapshots[{index}].manifest is required")
    if not name:
        raise ConnectCtlError(f"{path}: snapshots[{index}].name is required")
    if not isinstance(config, dict):
        raise ConnectCtlError(f"{path}: snapshots[{index}].config must be a mapping")
    return TemplateSnapshot(
        manifest=manifest,
        name=name,
        config=dict(sorted(config.items())),
    )


def _manifest_path(repo_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    return path


def _output_path(repo_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def _assert_inside_repo(repo_root: Path, path: Path) -> None:
    try:
        path.resolve().relative_to(repo_root)
    except ValueError as e:
        raise ConnectCtlError(
            f"Template snapshot path escapes repo root: {path}"
        ) from e


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)
