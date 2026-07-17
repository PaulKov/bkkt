from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Tuple

from ..exceptions import RenderError
from ..template_runtime import FunctionContext, TemplateRuntime
from ..utils import resolve_placeholders
from ..utils.placeholders import PlaceholderTrace


def resolve_rendered_name_and_config(
    name: str,
    config: Mapping[str, Any],
    ctx_flat: Mapping[str, Any],
    *,
    env_file: Path,
    template_runtime: TemplateRuntime | None = None,
    function_context: FunctionContext | None = None,
) -> Tuple[str, Dict[str, Any], PlaceholderTrace]:
    """Resolve placeholders in name and config and return trace of used keys."""

    trace = PlaceholderTrace()
    try:
        resolved_name = resolve_placeholders(
            name,
            ctx_flat,
            trace=trace,
            template_runtime=template_runtime,
            function_context=function_context,
        )
        resolved_config = resolve_placeholders(
            dict(config),
            ctx_flat,
            trace=trace,
            template_runtime=template_runtime,
            function_context=function_context,
        )
    except Exception as e:  # pragma: no cover (depends on placeholder engine details)
        raise RenderError(f"Placeholder resolution failed for {env_file}: {e}") from e

    if not isinstance(resolved_config, Mapping):
        raise RenderError(f"Resolved config must be an object for {env_file}")

    return str(resolved_name), dict(resolved_config), trace
