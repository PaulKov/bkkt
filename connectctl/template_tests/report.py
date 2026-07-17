from __future__ import annotations

from ..settings_models import Settings
from .diff import TemplateSnapshotDiffService
from .loader import TemplateTestLoader
from .models import TemplateWorkbenchReport
from .runner import TemplateTestRunner


class TemplateWorkbenchReportService:
    """Builds an MR-ready read-only report for template authoring checks."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repo_root = settings.repo.root.resolve()

    def report(
        self,
        *,
        pattern: str | None = None,
        snapshot_file: str | None = None,
    ) -> TemplateWorkbenchReport:
        cases = TemplateTestLoader(self.repo_root, pattern=pattern).load()
        tests = TemplateTestRunner(self.settings).run(cases)
        snapshots = TemplateSnapshotDiffService(self.settings).diff(
            snapshot_file=snapshot_file
        )
        return TemplateWorkbenchReport(tests=tests, snapshots=snapshots)
