from __future__ import annotations

from typing import Any, Mapping, Optional

from ..exceptions import ConnectCtlError
from ..template_runtime import FunctionContext, TemplateRuntime
from .placeholders_models import PlaceholderTrace


_DEFAULT_RUNTIME = TemplateRuntime.builtins_only()


def _eval_fn_placeholder(
    inner: str,
    context: Mapping[str, Any],
    trace: Optional[PlaceholderTrace] = None,
    *,
    template_runtime: TemplateRuntime | None = None,
    function_context: FunctionContext | None = None,
) -> str:
    """Backward-compatible facade for evaluating `${fn:...}` placeholders."""

    runtime = template_runtime or _DEFAULT_RUNTIME
    try:
        return runtime.evaluate(
            inner,
            context,
            trace=trace,
            function_context=function_context,
        )
    except ConnectCtlError as e:
        raise ValueError(str(e)) from e
