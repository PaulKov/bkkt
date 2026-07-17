from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Literal

from ..template_runtime.models import FunctionDescriptor
from ..template_runtime.signature import annotation_name, matches_annotation, type_name


Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class FunctionRunIssue:
    """Contract issue detected before executing `bkkt functions run`."""

    code: str
    severity: Severity
    function: str
    parameter: str | None
    expected: str | None = None
    actual_type: str | None = None
    message: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "function": self.function,
            "parameter": self.parameter,
            "expected": self.expected,
            "actual_type": self.actual_type,
            "message": self.message,
        }


@dataclass(frozen=True)
class FunctionRunPreflightResult:
    """Pre-execution contract result for one local function run."""

    issues: tuple[FunctionRunIssue, ...] = ()

    @property
    def status(self) -> str:
        return (
            "failed"
            if any(issue.severity == "error" for issue in self.issues)
            else "ok"
        )

    @property
    def exit_code(self) -> int:
        return 1 if self.status == "failed" else 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "issues": [issue.to_payload() for issue in self.issues],
        }


class FunctionRunPreflight:
    """Validates explicit `functions run` arguments before executing Python."""

    def validate(
        self,
        descriptor: FunctionDescriptor,
        *,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> FunctionRunPreflightResult:
        signature = inspect.signature(descriptor.fn)
        try:
            bound = signature.bind(*args, **kwargs)
        except TypeError as e:
            return FunctionRunPreflightResult(
                issues=(
                    FunctionRunIssue(
                        code="function_signature_error",
                        severity="error",
                        function=descriptor.name,
                        parameter=None,
                        message=(
                            f"Function {descriptor.name!r} call does not match "
                            f"its signature: {e}"
                        ),
                    ),
                )
            )

        issues: list[FunctionRunIssue] = []
        for name, value in bound.arguments.items():
            if name == "ctx":
                continue
            parameter = signature.parameters.get(name)
            if parameter is None:
                continue
            expected = annotation_name(parameter.annotation)
            if expected not in {"str", "int", "float", "bool"}:
                continue
            if matches_annotation(value, expected):
                continue
            issues.append(
                FunctionRunIssue(
                    code="function_arg_type_mismatch",
                    severity="error",
                    function=descriptor.name,
                    parameter=name,
                    expected=expected,
                    actual_type=type_name(value),
                    message=(
                        f"Function {descriptor.name!r} parameter {name!r} must be "
                        f"{expected}, got {type_name(value)}."
                    ),
                )
            )
        return FunctionRunPreflightResult(issues=tuple(issues))
