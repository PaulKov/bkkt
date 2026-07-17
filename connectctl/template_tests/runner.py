from __future__ import annotations

from pathlib import Path

from ..rendering.factory import build_renderer
from ..settings_models import Settings
from .models import (
    TemplateMismatch,
    TemplateTestCase,
    TemplateTestResult,
    TemplateTestSuite,
)


class TemplateTestRunner:
    """Runs golden render tests through the production renderer."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.renderer = build_renderer(settings)

    def run(self, cases: tuple[TemplateTestCase, ...]) -> TemplateTestSuite:
        return TemplateTestSuite(tuple(self._run_one(case) for case in cases))

    def _run_one(self, case: TemplateTestCase) -> TemplateTestResult:
        try:
            result = self.renderer.render(_manifest_path(self.settings.repo.root, case))
            mismatches: list[TemplateMismatch] = []
            if (
                case.expect_name is not None
                and result.manifest.name != case.expect_name
            ):
                mismatches.append(
                    TemplateMismatch(
                        key="name",
                        expected=case.expect_name,
                        actual=result.manifest.name,
                    )
                )
            for key, expected in (case.expect_config or {}).items():
                actual = result.manifest.config.get(key)
                if actual != expected:
                    mismatches.append(
                        TemplateMismatch(
                            key=f"config.{key}",
                            expected=expected,
                            actual=actual,
                        )
                    )
            if case.expect_full_config:
                expected_config = case.expect_config or {}
                for key in sorted(set(result.manifest.config) - set(expected_config)):
                    mismatches.append(
                        TemplateMismatch(
                            key=f"config.{key}",
                            expected=None,
                            actual=result.manifest.config.get(key),
                        )
                    )
            return TemplateTestResult(
                case=case,
                status="failed" if mismatches else "passed",
                mismatches=tuple(mismatches),
            )
        except Exception as e:
            return TemplateTestResult(case=case, status="failed", error=str(e))


def _manifest_path(repo_root: Path, case: TemplateTestCase) -> Path:
    path = Path(case.manifest)
    if not path.is_absolute():
        path = repo_root / path
    return path
