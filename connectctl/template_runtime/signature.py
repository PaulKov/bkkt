from __future__ import annotations

import inspect
from typing import Any

from ..exceptions import ConnectCtlError


SCALAR_ANNOTATIONS = {"str", "int", "float", "bool"}


class FunctionSignatureValidator:
    """Runtime type checks for repo-local function calls.

    The renderer executes trusted Python, but user-facing failures should still
    point to the function argument that broke the contract instead of surfacing a
    random Python `TypeError` from inside user code.
    """

    def validate_call(
        self,
        *,
        function: str,
        signature: inspect.Signature,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        expression: str,
    ) -> None:
        try:
            bound = signature.bind(*args, **kwargs)
        except TypeError as e:
            raise ConnectCtlError(
                f"function_signature_error: Function {function!r} call {expression!r} "
                f"does not match its signature: {e}"
            ) from e

        for name, value in bound.arguments.items():
            if name == "ctx":
                continue
            parameter = signature.parameters.get(name)
            if parameter is None:
                continue
            expected = annotation_name(parameter.annotation)
            if expected not in SCALAR_ANNOTATIONS:
                continue
            if not matches_annotation(value, expected):
                raise ConnectCtlError(
                    "function_arg_type_mismatch: "
                    f"Function {function!r} parameter {name!r} must be {expected}, "
                    f"got {type_name(value)} while evaluating {expression!r}."
                )

    def validate_return(
        self,
        *,
        function: str,
        signature: inspect.Signature,
        value: Any,
        expression: str,
    ) -> None:
        expected = annotation_name(signature.return_annotation)
        if expected not in SCALAR_ANNOTATIONS:
            return
        if not matches_annotation(value, expected):
            raise ConnectCtlError(
                "function_return_type_mismatch: "
                f"Function {function!r} must return {expected}, got "
                f"{type_name(value)} while evaluating {expression!r}."
            )


def annotation_name(annotation: Any) -> str:
    if annotation is inspect.Signature.empty:
        return ""
    if isinstance(annotation, str):
        return annotation.rsplit(".", 1)[-1]
    return getattr(annotation, "__name__", str(annotation).rsplit(".", 1)[-1])


def matches_annotation(value: Any, expected: str) -> bool:
    if expected == "bool":
        return isinstance(value, bool)
    if expected == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "str":
        return isinstance(value, str)
    return True


def type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    return type(value).__name__
