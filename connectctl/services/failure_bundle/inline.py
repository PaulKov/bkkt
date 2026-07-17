from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .models import FailureRemediation
from .utils import string_or_none

_INLINE_REMEDIATION_ATTR = "__bkkt_inline_remediation__"


def attach_inline_remediation(
    error: BaseException,
    *,
    remediation: FailureRemediation,
    bundle_dir: Path | None = None,
) -> None:
    payload = remediation.as_payload()
    payload["bundle_dir"] = str(bundle_dir) if bundle_dir is not None else None
    payload["readme_path"] = (
        str(bundle_dir / "README.md") if bundle_dir is not None else None
    )
    setattr(error, _INLINE_REMEDIATION_ATTR, payload)


def get_inline_remediation(error: BaseException) -> Mapping[str, Any] | None:
    payload = getattr(error, _INLINE_REMEDIATION_ATTR, None)
    if isinstance(payload, Mapping):
        return payload
    return None


def format_inline_remediation_lines(
    error: BaseException,
    *,
    max_actions: int = 2,
    max_commands: int = 2,
) -> list[str]:
    payload = get_inline_remediation(error)
    if not payload:
        return []

    summary = string_or_none(payload.get("summary"))
    category = string_or_none(payload.get("category")) or "generic"
    actions = [
        str(item).strip()
        for item in (payload.get("actions") or [])
        if string_or_none(item) is not None
    ]
    commands = [
        str(item).strip()
        for item in (payload.get("commands") or [])
        if string_or_none(item) is not None
    ]
    references = [
        str(item).strip()
        for item in (payload.get("references") or [])
        if string_or_none(item) is not None
    ]
    readme_path = string_or_none(payload.get("readme_path"))

    lines: list[str] = []
    if summary:
        lines.append(f"What to do next [{category}]: {summary}")
    else:
        lines.append(f"What to do next [{category}]")

    for action in actions[: max(0, max_actions)]:
        lines.append(f"- {action}")
    if len(actions) > max_actions:
        lines.append(
            f"- ... +{len(actions) - max_actions} more action(s) in bundle README"
        )

    if commands:
        lines.append("Try:")
        for item in commands[: max(0, max_commands)]:
            lines.append(f"  {item}")
        if len(commands) > max_commands:
            lines.append(
                f"  ... +{len(commands) - max_commands} more command(s) in bundle README"
            )

    if readme_path:
        lines.append(f"Full remediation: {readme_path}")
    elif references:
        lines.append(f"Reference: {references[0]}")

    return lines
