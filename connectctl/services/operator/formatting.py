from __future__ import annotations

from typing import Any

from ...output import OutputFormat, write_payload, write_text


def emit_extended_output(
    payload: dict[str, Any],
    *,
    output: str,
    text: str,
    markdown: str | None = None,
    mermaid: str | None = None,
) -> None:
    fmt = str(output or "text").strip().lower()
    if fmt == "json":
        write_payload(payload, fmt=OutputFormat.json)
        return
    if fmt == "yaml":
        write_payload(payload, fmt=OutputFormat.yaml)
        return
    if fmt == "markdown":
        write_text(markdown if markdown is not None else text)
        return
    if fmt == "mermaid":
        write_text(mermaid if mermaid is not None else text)
        return
    write_text(text)


def join_csv(values: Any) -> str:
    if not values:
        return "-"
    if isinstance(values, str):
        return values or "-"
    return ", ".join(str(v) for v in values if str(v)) or "-"


__all__ = ["emit_extended_output", "join_csv"]
