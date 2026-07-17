from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..models import ConnectorManifest


@dataclass(frozen=True)
class TopicInference:
    consumed_topics: Optional[List[str]]
    consumed_pattern: Optional[str]
    produced_topics: Optional[List[str]]
    produced_pattern: Optional[str]


_JAVA_GROUP_RE = re.compile(r"\$(\d+)")


def _maybe_list(x: Optional[str]) -> Optional[List[str]]:
    if not x:
        return None
    parts = [p.strip() for p in x.split(",") if p.strip()]
    return parts or None


def _topic2table_topics(raw: Optional[str]) -> Optional[List[str]]:
    topics: List[str] = []
    for item in _maybe_list(raw) or []:
        if "=" not in item:
            continue
        topic, _table = item.split("=", 1)
        topic = topic.strip()
        if topic:
            topics.append(topic)
    return topics or None


def _java_to_python_repl(repl: str) -> str:
    # Java RegexRouter uses $1, $2...; python re.sub uses \1, \2...
    return _JAVA_GROUP_RE.sub(lambda m: "\\" + m.group(1), repl)


def _replacement_to_output_pattern(repl: str) -> str:
    """Heuristic: convert RegexRouter replacement into a regex pattern.

    This is best-effort and intentionally conservative (may be broader than needed).
    """
    # Treat $$ as literal $
    repl = repl.replace("$$", "$")

    out_parts: List[str] = []
    pos = 0
    for m in _JAVA_GROUP_RE.finditer(repl):
        lit = repl[pos : m.start()]
        out_parts.append(re.escape(lit))
        out_parts.append(r".+")
        pos = m.end()
    out_parts.append(re.escape(repl[pos:]))
    return "^" + "".join(out_parts) + "$"


def _regex_router_chain(cfg: dict) -> List[Tuple[str, str]]:
    """Return a list of (regex, replacement) for RegexRouter transforms in order."""
    names = _maybe_list(cfg.get("transforms")) or []
    chain: List[Tuple[str, str]] = []
    for name in names:
        t = cfg.get(f"transforms.{name}.type", "")
        if t != "org.apache.kafka.connect.transforms.RegexRouter":
            continue
        regex = cfg.get(f"transforms.{name}.regex")
        repl = cfg.get(f"transforms.{name}.replacement")
        if not regex or repl is None:
            continue
        chain.append((str(regex), str(repl)))
    return chain


def _debezium_table_topics(cfg: dict, topic_prefix: str) -> Optional[List[str]]:
    """Return exact Debezium data topics when the table include-list is explicit."""

    raw_tables = cfg.get("table.include.list") or cfg.get("table.whitelist")
    tables = _maybe_list(str(raw_tables)) if raw_tables is not None else None
    if not tables:
        return None

    topics: List[str] = []
    for table in tables:
        table = table.strip()
        if not table:
            continue
        topics.append(f"{topic_prefix}.{table}")
    return topics or None


def infer_topics_from_config(cfg: dict) -> TopicInference:
    """Infer consumed/produced topics from common connector config keys.

    This is best-effort and covers a few key patterns:
    - Debezium sources (topic.prefix)
    - Sink connectors (topics / topics.regex)
    - RegexRouter SMT on sources (renamed produced topics)
    """
    cls = cfg.get("connector.class", "") or ""

    # Heuristic: source vs sink
    is_debezium = "debezium" in cls.lower()
    is_sink = any(
        x in cls for x in ["Sink", "IcebergSinkConnector", "JdbcSinkConnector"]
    ) or ("sink" in cls.lower())

    consumed_topics: Optional[List[str]] = None
    consumed_pattern: Optional[str] = None
    produced_topics: Optional[List[str]] = None
    produced_pattern: Optional[str] = None

    # Sink-like: reads from Kafka
    if is_sink:
        consumed_topics = _maybe_list(cfg.get("topics"))
        consumed_pattern = cfg.get("topics.regex")
        if not consumed_topics:
            consumed_topics = _topic2table_topics(cfg.get("topic2TableMap"))

    # Debezium-like source: writes to Kafka using topic.prefix
    if is_debezium and not is_sink:
        tp = cfg.get("topic.prefix")
        if tp:
            produced_topics = _debezium_table_topics(cfg, str(tp))
            if not produced_topics:
                produced_pattern = rf"^{re.escape(str(tp))}\\..+$"

    # Generic source connectors often use a single explicit `topic` key.
    if not is_sink and not produced_topics and not produced_pattern:
        explicit_topic = cfg.get("topic")
        if explicit_topic:
            produced_topics = _maybe_list(str(explicit_topic))

    # Apply RegexRouter transforms to produced topics/pattern (source side)
    if (produced_topics or produced_pattern) and not is_sink:
        routers = _regex_router_chain(cfg)
        if routers:
            # If we have explicit topics, transform them deterministically
            if produced_topics:
                cur = produced_topics
                for regex, repl in routers:
                    py_repl = _java_to_python_repl(repl)
                    try:
                        cur = [re.sub(regex, py_repl, t) for t in cur]
                    except re.error:
                        # If regex is invalid for python, keep original
                        continue
                produced_topics = cur

            # If we only have a pattern, approximate output pattern from the last router replacement
            if produced_pattern and not produced_topics:
                # Use the last router, since it defines the final topic name
                _, repl = routers[-1]
                produced_pattern = _replacement_to_output_pattern(repl)

    return TopicInference(
        consumed_topics=consumed_topics,
        consumed_pattern=consumed_pattern,
        produced_topics=produced_topics,
        produced_pattern=produced_pattern,
    )


def infer_topics(manifest: ConnectorManifest) -> TopicInference:
    """Backward-compatible manifest wrapper around infer_topics_from_config()."""

    return infer_topics_from_config(manifest.config)
