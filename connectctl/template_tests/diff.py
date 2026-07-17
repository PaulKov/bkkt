from __future__ import annotations

from typing import Iterable

from ..rendering.factory import build_renderer
from ..settings_models import Settings
from .models import (
    TemplateSnapshot,
    TemplateSnapshotDiff,
    TemplateSnapshotDiffReport,
)
from .snapshot import load_snapshot_file


class TemplateSnapshotDiffService:
    """Compares stored template snapshots with current rendered manifests."""

    DEFAULT_GLOB = "bkkt/templates/snapshots/**/*.yaml"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repo_root = settings.repo.root.resolve()
        self.renderer = build_renderer(settings)

    def diff(self, *, snapshot_file: str | None = None) -> TemplateSnapshotDiffReport:
        snapshots = tuple(self._load_snapshots(snapshot_file=snapshot_file))
        diffs: list[TemplateSnapshotDiff] = []
        for snapshot in snapshots:
            current = self.renderer.render(self.repo_root / snapshot.manifest).manifest
            if current.name != snapshot.name:
                diffs.append(
                    TemplateSnapshotDiff(
                        manifest=snapshot.manifest,
                        key="name",
                        expected=snapshot.name,
                        actual=current.name,
                    )
                )
            expected_config = snapshot.config
            actual_config = current.config
            for key in sorted(set(expected_config) | set(actual_config)):
                expected = expected_config.get(key)
                actual = actual_config.get(key)
                if expected != actual:
                    diffs.append(
                        TemplateSnapshotDiff(
                            manifest=snapshot.manifest,
                            key=f"config.{key}",
                            expected=expected,
                            actual=actual,
                        )
                    )
        return TemplateSnapshotDiffReport(
            diffs=tuple(sorted(diffs)),
            snapshots=len(snapshots),
        )

    def _load_snapshots(
        self, *, snapshot_file: str | None = None
    ) -> Iterable[TemplateSnapshot]:
        if snapshot_file:
            yield from load_snapshot_file(self.repo_root, snapshot_file)
            return
        for path in sorted(self.repo_root.glob(self.DEFAULT_GLOB)):
            yield from load_snapshot_file(self.repo_root, path)
