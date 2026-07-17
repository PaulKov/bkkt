from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

from ..logging_utils import get_logger
from ..utils import flatten_dict
from .renderer_sensitive import is_sensitive_var


@dataclass(frozen=True)
class ConfigKeySourceRow:
    key: str
    value_repr: str
    source: str
    chain: Tuple[str, ...]


def _compile_key_matchers(expr: Optional[str]) -> List[Callable[[str], bool]]:
    """Build a list of matchers for config keys.

    `expr` can contain multiple patterns separated by comma.
    Each pattern is treated as regex (search). If regex compilation fails,
    it falls back to case-insensitive substring match.
    """

    if not expr:
        return []

    parts = [p.strip() for p in str(expr).split(",") if p.strip()]
    out: List[Callable[[str], bool]] = []
    for p in parts:
        try:
            rx = re.compile(p)

            def _rx_match(s: str, _rx: re.Pattern[str] = rx) -> bool:
                return _rx.search(s) is not None

            out.append(_rx_match)
        except re.error:
            low = p.lower()

            def _substr_match(s: str, _low: str = low) -> bool:
                return _low in (s or "").lower()

            out.append(_substr_match)
    return out


def _matches_any(key: str, matchers: Sequence[Callable[[str], bool]]) -> bool:
    if not matchers:
        return True
    return any(m(key) for m in matchers)


def _repr_value(key: str, value: Any, *, max_len: int = 160) -> str:
    """Human-readable value representation for logs.

    - masks sensitive keys
    - JSON encodes non-strings
    - truncates long values
    """

    if is_sensitive_var(key):
        return '"***"'

    if isinstance(value, str):
        s = value
        if len(s) > max_len:
            s = s[: max_len - 3] + "..."
        return json.dumps(s, ensure_ascii=False)

    try:
        s = json.dumps(value, ensure_ascii=False)
    except Exception:
        s = repr(value)

    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


def build_config_key_source_rows(
    *,
    config: Mapping[str, Any],
    config_sources: Mapping[str, str],
    config_sources_chain: Mapping[str, Sequence[str]],
    keys_filter: Optional[str] = None,
    max_rows: int = 200,
) -> Tuple[Tuple[ConfigKeySourceRow, ...], int]:
    """Build rows for explain-vars.

    Returns: (rows, truncated_count)
    """

    matchers = _compile_key_matchers(keys_filter)
    flat = flatten_dict(config)

    keys = [k for k in sorted(flat.keys()) if _matches_any(k, matchers)]
    truncated = 0
    if max_rows and max_rows > 0 and len(keys) > max_rows:
        truncated = len(keys) - max_rows
        keys = keys[:max_rows]

    rows: List[ConfigKeySourceRow] = []
    for k in keys:
        v = flat.get(k)
        src = str(config_sources.get(k) or "(unknown)")
        chain_raw = list(config_sources_chain.get(k) or [])
        if not chain_raw and src != "(unknown)":
            chain_raw = [src]
        # Compress duplicates (can happen if some tooling reuses same label)
        chain: List[str] = []
        for s in chain_raw:
            if not chain or chain[-1] != s:
                chain.append(str(s))

        rows.append(
            ConfigKeySourceRow(
                key=str(k),
                value_repr=_repr_value(str(k), v),
                source=src,
                chain=tuple(chain),
            )
        )

    return tuple(rows), truncated


def summarize_sources(rows: Iterable[ConfigKeySourceRow]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        out[r.source] = out.get(r.source, 0) + 1
    return out


def log_config_key_sources(
    rr: Any,
    repo_root: Path,
    *,
    keys_filter: Optional[str] = None,
    max_rows: int = 200,
    logger=None,
) -> None:
    """Логирует explain-vars для финального конфига коннектора.

    Печатается по *leaf*-ключам (flattened dot-keys): например transforms.unwrap.type.
    """

    log = get_logger(logger)

    config = getattr(getattr(rr, "manifest", None), "config", None)
    if not isinstance(config, Mapping):
        log.info("Explain-vars: config отсутствует или не является объектом")
        return

    config_sources = getattr(rr, "config_sources", {}) or {}
    config_sources_chain = getattr(rr, "config_sources_chain", {}) or {}

    rows, truncated = build_config_key_source_rows(
        config=config,
        config_sources=config_sources,
        config_sources_chain=config_sources_chain,
        keys_filter=keys_filter,
        max_rows=max_rows,
    )

    if not rows:
        log.info("Explain-vars: ключи не найдены (возможно фильтр слишком строгий)")
        return

    summary = summarize_sources(rows)
    log.info("Config sources summary (last-writer, leaf-keys):")
    for src, cnt in sorted(summary.items(), key=lambda x: (-x[1], x[0])):
        log.info(" - %s: %s", src, cnt)

    log.info("Config key sources (leaf-keys):")
    for r in rows:
        if len(r.chain) > 1:
            chain = " -> ".join(r.chain)
            log.info(
                " - %s = %s  [source: %s]  [chain: %s]",
                r.key,
                r.value_repr,
                r.source,
                chain,
            )
        else:
            log.info(" - %s = %s  [source: %s]", r.key, r.value_repr, r.source)

    if truncated:
        log.info(
            "... и ещё %s ключ(ей) (увеличьте --explain-vars-max или уточните --explain-vars-keys)",
            truncated,
        )
