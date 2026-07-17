from __future__ import annotations

import ast
import inspect
from typing import Any, Mapping

from ..exceptions import ConnectCtlError
from ..runtime_safety import RuntimeSafetyPolicy
from ..utils.placeholders_models import PlaceholderTrace
from .api import FunctionContext
from .registry import FunctionRegistry
from .signature import FunctionSignatureValidator


class FunctionEvaluator:
    """Parses and executes safe `${fn:...}` expressions."""

    def __init__(
        self,
        registry: FunctionRegistry,
        safety: RuntimeSafetyPolicy | None = None,
    ) -> None:
        self.registry = registry
        self.safety = safety or RuntimeSafetyPolicy()

    def evaluate(
        self,
        inner: str,
        context: Mapping[str, Any],
        *,
        trace: PlaceholderTrace | None = None,
        function_context: FunctionContext | None = None,
    ) -> str:
        expr = inner.split(":", 1)[1].strip()
        try:
            node = ast.parse(expr, mode="eval")
        except Exception as e:
            raise ConnectCtlError(
                f"Invalid function placeholder expression {expr!r}. "
                "Use syntax like ${fn:name(arg, key='value')}."
            ) from e

        if not isinstance(node.body, ast.Call) or not isinstance(
            node.body.func, (ast.Name, ast.Attribute)
        ):
            raise ConnectCtlError(
                f"Only simple function calls are allowed in ${{fn:...}}, got {expr!r}."
            )

        function_name = self._call_name(node.body.func)
        descriptor = self.registry.get(function_name)
        args = [self._eval_arg(arg, context, trace=trace) for arg in node.body.args]
        kwargs = {}
        for kw in node.body.keywords:
            if kw.arg is None:
                raise ConnectCtlError("**kwargs are not allowed in ${fn:...}")
            kwargs[kw.arg] = self._eval_arg(kw.value, context, trace=trace)

        fn = descriptor.fn
        sig = inspect.signature(fn)
        if "ctx" in sig.parameters and "ctx" not in kwargs:
            kwargs["ctx"] = function_context or FunctionContext.from_flat_context(
                context
            )
        validator = FunctionSignatureValidator()
        validator.validate_call(
            function=descriptor.name,
            signature=sig,
            args=tuple(args),
            kwargs=kwargs,
            expression=expr,
        )

        try:
            result = self.safety.run_callable(
                kind="function",
                name=descriptor.name,
                capabilities=descriptor.capabilities,
                timeout_ms=descriptor.timeout_ms,
                call=lambda: fn(*args, **kwargs),
            )
        except Exception as e:
            if isinstance(e, ConnectCtlError):
                raise
            raise ConnectCtlError(
                f"Function {descriptor.name!r} failed while evaluating {expr!r}: {e}"
            ) from e

        validator.validate_return(
            function=descriptor.name,
            signature=sig,
            value=result,
            expression=expr,
        )
        if not isinstance(result, (str, int, float, bool)):
            raise ConnectCtlError(
                f"Function {descriptor.name!r} must return scalar str/int/float/bool, "
                f"got {type(result).__name__}."
            )
        return str(result)

    def _eval_arg(
        self,
        node: ast.AST,
        context: Mapping[str, Any],
        *,
        trace: PlaceholderTrace | None = None,
    ) -> Any:
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            return self._context_value(node.id, context, trace=trace)

        if isinstance(node, ast.Attribute):
            return self._context_value(
                self._attr_to_dot_key(node), context, trace=trace
            )

        raise ConnectCtlError(
            f"Unsupported argument in function placeholder: {type(node).__name__}. "
            "Use literals or context variables only."
        )

    def _context_value(
        self,
        key: str,
        context: Mapping[str, Any],
        *,
        trace: PlaceholderTrace | None = None,
    ) -> Any:
        if key not in context:
            raise ConnectCtlError(
                f"Unknown function argument variable {key!r}. "
                "Use `bkkt vars explain <manifest>` to inspect available variables."
            )
        if trace is not None:
            trace.add(key, "fn_arg", str(context[key]))
        return context[key]

    def _attr_to_dot_key(self, node: ast.AST) -> str:
        parts: list[str] = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            return ".".join(reversed(parts))
        raise ConnectCtlError(
            "Unsupported attribute expression in function placeholder"
        )

    def _call_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return self._attr_to_dot_key(node)
        raise ConnectCtlError("Unsupported function name in function placeholder")
