from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class TemplateTestCase:
    name: str
    manifest: str
    expect_name: str | None = None
    expect_config: dict[str, Any] | None = None
    expect_full_config: bool = False
    source_path: Path | None = None


@dataclass(frozen=True)
class TemplateMismatch:
    key: str
    expected: Any
    actual: Any

    def to_payload(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass(frozen=True)
class TemplateTestResult:
    case: TemplateTestCase
    status: Literal["passed", "failed"]
    mismatches: tuple[TemplateMismatch, ...] = ()
    error: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.case.name,
            "manifest": self.case.manifest,
            "status": self.status,
            "mismatches": [item.to_payload() for item in self.mismatches],
            "error": self.error,
            "source_path": (
                str(self.case.source_path) if self.case.source_path else None
            ),
        }


@dataclass(frozen=True)
class TemplateTestSuite:
    results: tuple[TemplateTestResult, ...]

    @property
    def failed(self) -> int:
        return sum(1 for item in self.results if item.status == "failed")

    @property
    def passed(self) -> int:
        return sum(1 for item in self.results if item.status == "passed")

    @property
    def status(self) -> str:
        return "failed" if self.failed else "ok"

    @property
    def exit_code(self) -> int:
        return 1 if self.failed else 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": {
                "total": len(self.results),
                "passed": self.passed,
                "failed": self.failed,
            },
            "cases": [item.to_payload() for item in self.results],
        }


@dataclass(frozen=True)
class TemplateSnapshot:
    manifest: str
    name: str
    config: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest,
            "name": self.name,
            "config": dict(sorted(self.config.items())),
        }


@dataclass(frozen=True)
class TemplateSnapshotPlan:
    snapshot: TemplateSnapshot
    status: str = "planned"
    output_file: str | None = None

    @property
    def config_keys(self) -> int:
        return len(self.snapshot.config)

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": "template_snapshot",
            "status": self.status,
            "manifest": self.snapshot.manifest,
            "output_file": self.output_file,
            "summary": {"config_keys": self.config_keys},
            "snapshot": self.snapshot.to_payload(),
        }


@dataclass(frozen=True, order=True)
class TemplateSnapshotDiff:
    manifest: str
    key: str
    expected: Any
    actual: Any

    def to_payload(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest,
            "key": self.key,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass(frozen=True)
class TemplateSnapshotDiffReport:
    diffs: tuple[TemplateSnapshotDiff, ...]
    snapshots: int

    @property
    def changed(self) -> int:
        return len(self.diffs)

    @property
    def status(self) -> str:
        return "failed" if self.changed else "ok"

    @property
    def exit_code(self) -> int:
        return 1 if self.changed else 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": "template_snapshot_diff",
            "status": self.status,
            "summary": {
                "snapshots": self.snapshots,
                "changed": self.changed,
            },
            "diffs": [item.to_payload() for item in self.diffs],
        }


@dataclass(frozen=True)
class TemplateWorkbenchReport:
    tests: TemplateTestSuite
    snapshots: TemplateSnapshotDiffReport

    @property
    def status(self) -> str:
        return (
            "failed"
            if self.tests.exit_code != 0 or self.snapshots.exit_code != 0
            else "ok"
        )

    @property
    def exit_code(self) -> int:
        return 1 if self.status == "failed" else 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": "template_workbench_report",
            "status": self.status,
            "tests": self.tests.to_payload(),
            "snapshots": self.snapshots.to_payload(),
        }
