from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from ..template_runtime import TemplateRuntime
from ..utils import flatten_dict


Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class FunctionCallIssue:
    code: str
    severity: Severity
    function: str
    parameter: str | None
    config_key: str
    expected: str | None = None
    actual_type: str | None = None
    message: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "function": self.function,
            "parameter": self.parameter,
            "config_key": self.config_key,
            "expected": self.expected,
            "actual_type": self.actual_type,
            "message": self.message,
        }


@dataclass(frozen=True)
class FunctionCallValidationResult:
    manifest: str
    issues: tuple[FunctionCallIssue, ...]

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
        ordered = sorted(
            self.issues,
            key=lambda issue: (0 if issue.severity == "error" else 1, issue.config_key),
        )
        return {
            "status": self.status,
            "manifest": self.manifest,
            "summary": {
                "errors": sum(1 for issue in self.issues if issue.severity == "error"),
                "warnings": sum(
                    1 for issue in self.issues if issue.severity == "warning"
                ),
                "total": len(self.issues),
            },
            "issues": [issue.to_payload() for issue in ordered],
        }


class FunctionCallValidator:
    """Validates literal `${fn:...}` arguments against registered signatures."""

    def __init__(self, runtime: TemplateRuntime, *, repo_root: Path) -> None:
        self.runtime = runtime
        self.repo_root = repo_root.resolve()

    def validate_manifest(
        self, *, manifest_path: Path, config: Mapping[str, Any]
    ) -> FunctionCallValidationResult:
        issues: list[FunctionCallIssue] = []
        for config_key, value in flatten_dict(config).items():
            if not isinstance(value, str):
                continue
            for call in _extract_function_calls(value):
                issues.extend(self._validate_call(call, config_key=str(config_key)))
        return FunctionCallValidationResult(
            manifest=_relative(manifest_path, self.repo_root),
            issues=tuple(issues),
        )

    def _validate_call(
        self, call: "_FunctionCall", *, config_key: str
    ) -> list[FunctionCallIssue]:
        issues: list[FunctionCallIssue] = []
        try:
            descriptor = self.runtime.registry.get(call.name)
        except Exception as e:
            return [
                FunctionCallIssue(
                    code="function_not_registered",
                    severity="error",
                    function=call.name,
                    parameter=None,
                    config_key=config_key,
                    message=str(e),
                )
            ]
        signature = inspect.signature(descriptor.fn)
        parameters = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.name != "ctx"
        ]
        positional_parameters = [
            parameter
            for parameter in parameters
            if parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        for index, argument in enumerate(call.args):
            if index >= len(positional_parameters):
                continue
            issues.extend(
                _validate_argument(
                    function=call.name,
                    parameter=positional_parameters[index],
                    argument=argument,
                    config_key=config_key,
                )
            )
        for name, argument in call.kwargs.items():
            parameter = signature.parameters.get(name)
            if parameter is None or parameter.name == "ctx":
                continue
            issues.extend(
                _validate_argument(
                    function=call.name,
                    parameter=parameter,
                    argument=argument,
                    config_key=config_key,
                )
            )
        return issues


@dataclass(frozen=True)
class _FunctionCall:
    name: str
    args: tuple["_ArgumentValue", ...]
    kwargs: dict[str, "_ArgumentValue"]


@dataclass(frozen=True)
class _ArgumentValue:
    value: Any | None
    type_name: str
    is_literal: bool


def _validate_argument(
    *,
    function: str,
    parameter: inspect.Parameter,
    argument: _ArgumentValue,
    config_key: str,
) -> list[FunctionCallIssue]:
    expected = _annotation_name(parameter.annotation)
    if expected not in {"str", "int", "float", "bool"}:
        return []
    if not argument.is_literal:
        return [
            FunctionCallIssue(
                code="function_arg_type_unknown",
                severity="warning",
                function=function,
                parameter=parameter.name,
                config_key=config_key,
                expected=expected,
                actual_type="unknown",
                message=(
                    f"Argument {parameter.name!r} for function {function!r} comes "
                    "from a variable/expression; BKKT cannot prove its type statically."
                ),
            )
        ]
    if argument.type_name == expected or (
        expected == "float" and argument.type_name == "int"
    ):
        return []
    return [
        FunctionCallIssue(
            code="function_arg_type_mismatch",
            severity="error",
            function=function,
            parameter=parameter.name,
            config_key=config_key,
            expected=expected,
            actual_type=argument.type_name,
            message=(
                f"Argument {parameter.name!r} for function {function!r} must be "
                f"{expected}, got {argument.type_name}."
            ),
        )
    ]


def _extract_function_calls(text: str) -> tuple[_FunctionCall, ...]:
    calls: list[_FunctionCall] = []
    for inner in _placeholder_inners(text):
        if not inner.startswith("fn:"):
            continue
        expr = inner.split(":", 1)[1].strip()
        try:
            parsed = ast.parse(expr, mode="eval")
        except SyntaxError:
            continue
        if not isinstance(parsed.body, ast.Call) or not isinstance(
            parsed.body.func, (ast.Name, ast.Attribute)
        ):
            continue
        call_name = _call_name(parsed.body.func)
        if not call_name:
            continue
        calls.append(
            _FunctionCall(
                name=call_name,
                args=tuple(_argument_value(arg) for arg in parsed.body.args),
                kwargs={
                    keyword.arg: _argument_value(keyword.value)
                    for keyword in parsed.body.keywords
                    if keyword.arg
                },
            )
        )
    return tuple(calls)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts: list[str] = []
        cur: ast.AST = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            return ".".join(reversed(parts))
    return ""


def _placeholder_inners(text: str) -> list[str]:
    inners: list[str] = []
    i = 0
    while i < len(text):
        start = text.find("${", i)
        if start < 0:
            break
        depth = 1
        j = start + 2
        while j < len(text):
            if text.startswith("${", j):
                depth += 1
                j += 2
                continue
            if text[j] == "}":
                depth -= 1
                if depth == 0:
                    inners.append(text[start + 2 : j])
                    i = j + 1
                    break
            j += 1
        else:
            break
    return inners


def _argument_value(node: ast.AST) -> _ArgumentValue:
    if isinstance(node, ast.Constant):
        return _ArgumentValue(
            value=node.value,
            type_name=_type_name(node.value),
            is_literal=True,
        )
    return _ArgumentValue(value=None, type_name="unknown", is_literal=False)


def _type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    return type(value).__name__


def _annotation_name(annotation: Any) -> str:
    if annotation is inspect.Signature.empty:
        return ""
    if isinstance(annotation, str):
        return annotation.rsplit(".", 1)[-1]
    return getattr(annotation, "__name__", str(annotation).rsplit(".", 1)[-1])


def _relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)
