from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class FunctionContractCase:
    name: str
    function: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] | None = None
    expect: Any = None
    manifest: str | None = None
    source_path: Path | None = None


@dataclass(frozen=True)
class FunctionContractResult:
    case: FunctionContractCase
    status: Literal["passed", "failed"]
    actual: Any | None = None
    error: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.case.name,
            "function": self.case.function,
            "status": self.status,
            "expected": self.case.expect,
            "actual": self.actual,
            "error": self.error,
            "source_path": (
                str(self.case.source_path) if self.case.source_path else None
            ),
        }


@dataclass(frozen=True)
class FunctionContractSuite:
    results: tuple[FunctionContractResult, ...]

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
