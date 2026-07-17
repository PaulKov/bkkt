from __future__ import annotations

from typing import Any, List, Optional, Tuple

from ..ports import ConnectApi


def _split_names_csv(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    out: List[str] = []
    for part in str(raw).split(","):
        p = part.strip()
        if p:
            out.append(p)
    # preserve order, drop dups
    seen: set[str] = set()
    uniq: List[str] = []
    for n in out:
        if n in seen:
            continue
        seen.add(n)
        uniq.append(n)
    return uniq


def _compile_name_regexps(regexps: Optional[List[str]]) -> List[Any]:
    if not regexps:
        return []
    import re as _re

    out = []
    for raw in regexps:
        s = str(raw).strip()
        if not s:
            continue
        out.append(_re.compile(s))
    return out


def _select_connectors(
    *,
    connect: ConnectApi,
    names_csv: Optional[str],
    regexps: Optional[List[str]],
    all_flag: bool,
) -> Tuple[List[str], List[str]]:
    """Resolve a connector selection against a Kafka Connect cluster.

    Returns:
      (selected_names_in_cluster_order, missing_explicit_names)
    """
    explicit = _split_names_csv(names_csv)
    patterns = _compile_name_regexps(regexps)
    needs_list = bool(all_flag or patterns)

    existing: List[str] = list(connect.list_connectors()) if needs_list else []
    existing_set = set(existing)

    selected: set[str] = set()

    if all_flag:
        selected |= existing_set

    for n in explicit:
        selected.add(n)

    if patterns:
        for n in existing:
            if any(p.search(n) for p in patterns):
                selected.add(n)

    ordered: List[str] = []
    for n in existing:
        if n in selected:
            ordered.append(n)

    # Do not declare explicit names missing based on `/connectors` list alone.
    # Kafka Connect workers may temporarily return stale list responses while
    # connector-specific `/status` and `/config` are already healthy on another
    # worker. Callers verify explicit names through direct connector endpoints.
    missing: List[str] = []
    for n in explicit:
        if n not in ordered:
            ordered.append(n)

    return ordered, missing
