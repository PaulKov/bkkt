from __future__ import annotations

import re
import shlex
from typing import Any, Mapping, Sequence


def slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "unknown"


def string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def dedupe_keep_order(items: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def command(*tokens: object) -> str:
    args = [str(token) for token in tokens if string_or_none(token) is not None]
    return shlex.join(args)


def cluster_group_from_payload(
    manifest_meta: Mapping[str, Any], routing_payload: Mapping[str, Any]
) -> str | None:
    cluster_group = string_or_none(manifest_meta.get("cluster_group"))
    if cluster_group:
        return cluster_group
    cluster = routing_payload.get("cluster")
    if isinstance(cluster, Mapping):
        return string_or_none(cluster.get("group"))
    return None


def selector_tokens_from_extra(extra: Mapping[str, Any]) -> tuple[str, ...]:
    tokens: list[str] = []
    names_csv = string_or_none(extra.get("names_csv"))
    if names_csv:
        tokens.extend(("--names", names_csv))
    for regexp in extra.get("regexp") or []:
        regexp_text = string_or_none(regexp)
        if regexp_text:
            tokens.extend(("--regexp", regexp_text))
    if bool(extra.get("all")):
        tokens.append("--all")
    return tuple(tokens)
