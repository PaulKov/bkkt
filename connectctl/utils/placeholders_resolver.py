from __future__ import annotations

import os
import re
from typing import Any, Dict, Mapping, Optional

from ..template_runtime import FunctionContext, TemplateRuntime
from .placeholders_functions import _eval_fn_placeholder
from .placeholders_models import PlaceholderTrace


# Variable token used in ${VAR} / ${VAR:-default} placeholders.
#
# IMPORTANT:
# - We resolve *BKKT* placeholders (vars/runtime_vars) and *OS env* placeholders.
# - We preserve Kafka Connect ConfigProvider placeholders intact, e.g. ${secretManager:...}.
# - The `:-default` form is allowed for BOTH BKKT vars and OS env vars.
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _resolve_str_once_nested(
    s: str,
    context: Mapping[str, Any],
    *,
    trace: Optional[PlaceholderTrace] = None,
    template_runtime: TemplateRuntime | None = None,
    function_context: FunctionContext | None = None,
) -> str:
    """Один проход по строке: замена только самых внутренних (innermost) ${...}.

    - Сохраняем Kafka Connect ConfigProvider плейсхолдеры (${secretManager:...}, ${file:...} и т.п.)
      в исходном виде (это важно для runtime-резолва на Connect worker).
    - Исключение: наши ${fn:...}/${py:...} — их вычисляем.
    - Поддерживаем дефолты: ${AWS_REGION:-eu-central-1} и ${debezium_snapshot_mode_init:-initial}
    """
    stack = []
    replacements = []  # (start, end, repl)
    i = 0
    while i < len(s):
        if s[i : i + 2] == "${":
            stack.append(i)
            i += 2
            continue

        if s[i] == "}" and stack:
            start = stack.pop()
            end = i
            inner = s[start + 2 : end]

            # Only resolve *innermost* placeholders in this pass.
            if "${" in inner:
                i += 1
                continue

            # Function placeholders (ours): resolve even though they contain ':'.
            if inner.startswith("fn:") or inner.startswith("py:"):
                rep = _eval_fn_placeholder(
                    inner,
                    context,
                    trace=trace,
                    template_runtime=template_runtime,
                    function_context=function_context,
                )
                replacements.append((start, end, rep))
                i += 1
                continue

            # Default value placeholder (BKKT vars OR env vars):
            #   ${AWS_REGION:-eu-central-1}
            #   ${debezium_snapshot_mode_init:-initial}
            #
            # We only treat it as a default-placeholder if the ONLY colon is the one from ':-'.
            # This keeps Kafka Connect ConfigProvider placeholders intact: ${secretManager:...}.
            if ":-" in inner and inner.count(":") == 1:
                var, default = inner.split(":-", 1)
                var = var.strip()
                if _NAME_RE.match(var):
                    src = None
                    val = None
                    if var in context:
                        val = context.get(var)
                        src = "context"
                    elif var in os.environ:
                        val = os.environ.get(var)
                        src = "os_env"

                    if val is None or str(val) == "":
                        val = default
                        src = "default"

                    if trace is not None:
                        trace.add(var, src or "default", str(val))
                    replacements.append((start, end, str(val)))
                    i += 1
                    continue

            # Keep Kafka Connect ConfigProvider placeholders intact, e.g. ${secretManager:...}
            if ":" in inner:
                i += 1
                continue

            if inner in context:
                val = str(context[inner])
                if trace is not None:
                    trace.add(inner, "context", val)
                replacements.append((start, end, val))
            elif inner in os.environ:
                val = str(os.environ.get(inner) or "")
                if trace is not None:
                    trace.add(inner, "os_env", val)
                replacements.append((start, end, val))
            else:
                if trace is not None:
                    trace.add(inner, "unresolved", None)

            i += 1
            continue

        i += 1

    if not replacements:
        return s

    # Apply from right to left so indices stay valid.
    out = s
    for start, end, rep in sorted(replacements, key=lambda t: t[0], reverse=True):
        out = out[:start] + rep + out[end + 1 :]

    return out


def _resolve_str_iter(
    s: str,
    context: Mapping[str, Any],
    *,
    trace: Optional[PlaceholderTrace] = None,
    template_runtime: TemplateRuntime | None = None,
    function_context: FunctionContext | None = None,
    max_passes: int = 25,
) -> str:
    """Resolve placeholders in a string iteratively (supports nested placeholders)."""
    cur = s
    for _ in range(max_passes):
        nxt = _resolve_str_once_nested(
            cur,
            context,
            trace=trace,
            template_runtime=template_runtime,
            function_context=function_context,
        )
        if nxt == cur:
            break
        cur = nxt
    return cur


def resolve_placeholders(
    obj: Any,
    context: Mapping[str, Any],
    trace: Optional[PlaceholderTrace] = None,
    *,
    template_runtime: TemplateRuntime | None = None,
    function_context: FunctionContext | None = None,
) -> Any:
    """Resolve ${var} placeholders using provided context.

    Features:
    - Resolves placeholders in BOTH keys and values for dictionaries.
    - Handles nested placeholders (e.g. config-provider placeholders with inner vars).
    - Supports safe function placeholders (${fn:...}) from a strict allow-list.
    - Supports environment-variable placeholders, including shell-style defaults:
        ${AWS_REGION} and ${AWS_REGION:-eu-central-1}
    - Safety: placeholders whose *innermost* key contains ':' are preserved (Kafka Connect ConfigProviders),
      except our ${fn:...} placeholders and the env-var default form (${VAR:-default}).
    - Unknown placeholders are left unchanged.

    Context supports dot-keys (use flatten_dict()).
    """
    if isinstance(obj, str):
        return _resolve_str_iter(
            obj,
            context,
            trace=trace,
            template_runtime=template_runtime,
            function_context=function_context,
        )

    if isinstance(obj, list):
        return [
            resolve_placeholders(
                v,
                context,
                trace=trace,
                template_runtime=template_runtime,
                function_context=function_context,
            )
            for v in obj
        ]

    if isinstance(obj, dict):
        out: Dict[Any, Any] = {}
        for k, v in obj.items():
            new_k = (
                _resolve_str_iter(
                    k,
                    context,
                    trace=trace,
                    template_runtime=template_runtime,
                    function_context=function_context,
                )
                if isinstance(k, str)
                else k
            )
            if new_k in out:
                raise ValueError(
                    f"Placeholder resolution produced duplicate key: {new_k!r}"
                )
            out[new_k] = resolve_placeholders(
                v,
                context,
                trace=trace,
                template_runtime=template_runtime,
                function_context=function_context,
            )
        return out

    return obj
