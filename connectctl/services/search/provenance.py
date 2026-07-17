from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Mapping, Tuple

from .. import connector_facts_iceberg as iceberg_facts
from ..connector_facts import parse_topic2table_map
from .models import SearchOccurrence

SourceIndex = Dict[str, Dict[str, Tuple[str, ...]]]


def config_source(key: str) -> str:
    return f'config("{key}")'


def sources_for_match(
    *,
    facts: Any,
    field_name: str,
    matched_values: Iterable[str],
    config_key: str | None = None,
) -> Tuple[str, ...]:
    if config_key:
        return (config_source(config_key),)
    index = build_source_index(facts)
    sources: list[str] = []
    field_index = index.get(field_name, {})
    for value in matched_values:
        sources.extend(field_index.get(str(value), ()))
    return _dedupe(sources)


def related_occurrences(
    *,
    facts: Any,
    query_value: str | None,
    ignore_case: bool,
    max_items: int = 12,
) -> Tuple[SearchOccurrence, ...]:
    if not query_value:
        return ()
    index = build_source_index(facts)
    occurrences: list[SearchOccurrence] = []
    seen: set[tuple[str, str, Tuple[str, ...]]] = set()

    def add(field: str, value: str, sources: Iterable[str]) -> None:
        clean_sources = _dedupe(sources)
        key = (field, value, clean_sources)
        if not clean_sources or key in seen:
            return
        seen.add(key)
        occurrences.append(
            SearchOccurrence(field=field, value=value, sources=clean_sources)
        )

    for field, values in index.items():
        for value, sources in values.items():
            if _occurrence_matches(
                field=field,
                value=value,
                query_value=query_value,
                ignore_case=ignore_case,
            ):
                add(field, value, sources)
            for source in sources:
                if _text_contains(source, query_value, ignore_case=ignore_case):
                    add("config.key", source, [source])

    return tuple(occurrences[:max_items])


def build_source_index(facts: Any) -> SourceIndex:
    cfg = dict(getattr(facts, "config", {}) or {})
    index: SourceIndex = {}

    def add(field: str, values: Iterable[Any], sources: Iterable[str]) -> None:
        clean_sources = _dedupe(sources)
        if not clean_sources:
            return
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            field_map = index.setdefault(field, {})
            field_map[text] = _dedupe([*field_map.get(text, ()), *clean_sources])

    add("name", [facts.name], ["connector.name"])
    add("origin", [facts.origin], ["search.origin"])
    add("env", facts.envs, ["search.scope"])
    add("cluster", facts.clusters, ["search.routing"])
    if facts.path:
        add("path", [facts.path], ["repo.path"])
    add("domain", [facts.domain], ["connector.name"])
    add("dataset", [facts.dataset], ["connector.name"])
    add("type", [facts.connector_type], ["connector.name"])
    add("system", [facts.system], ["connector.name"])
    add("layer", [facts.layer], ["connector.name"])
    add("mode", [facts.mode], ["connector.name"])
    add("kind", [facts.kind], ["connector.name"])

    _add_config_key_values(
        index, "db.host", cfg, ("database.hostname", "database.host", "connection.host")
    )
    _add_config_key_values(index, "db.port", cfg, ("database.port", "connection.port"))
    _add_config_key_values(
        index,
        "db.name",
        cfg,
        (
            "database.dbname",
            "database.names",
            "database.include.list",
            "database.name",
            "database.db.name",
        ),
    )
    _add_config_key_values(
        index, "db.schema", cfg, ("schema.include.list", "database.schema", "schema")
    )
    _add_config_key_values(
        index,
        "db.server",
        cfg,
        (
            "database.server.name",
            "database.server.id",
            "publication.name",
            "topic.prefix",
        ),
    )

    _index_source_tables(index, cfg)
    _index_sink_tables(index, cfg, facts=facts)
    _index_topics(index, cfg, facts=facts)

    _add_config_key_values(
        index,
        "sink.database",
        cfg,
        (
            "transforms.setTableName.db.name",
            "iceberg.db_name",
            "iceberg.db.name",
            "iceberg.tables.default-namespace",
            "database",
            "database.name",
        ),
    )
    for full_name in facts.sink_table_full_names():
        parsed = iceberg_facts.parse_full_table_name(full_name)
        if parsed is not None and parsed[0]:
            sources = _config_sources(
                iceberg_facts.table_sources(cfg, table=parsed[1], full_name=full_name)
            )
            add("sink.database", [parsed[0]], sources)

    _add_config_key_values(
        index,
        "sink.warehouse",
        cfg,
        (
            "iceberg.catalog.glue.warehouse",
            "iceberg.catalog.warehouse",
            "iceberg.warehouse",
        ),
    )

    # topics.any is a convenience union. Preserve original field provenance.
    for field_name in ("topics.consumed", "topics.produced", "topics.pattern"):
        for value, sources in index.get(field_name, {}).items():
            add("topics.any", [value], sources)

    return index


def _occurrence_matches(
    *, field: str, value: str, query_value: str, ignore_case: bool
) -> bool:
    if _text_contains(value, query_value, ignore_case=ignore_case):
        return True
    if field == "topics.pattern":
        flags = re.IGNORECASE if ignore_case else 0
        try:
            return re.search(value, query_value, flags=flags) is not None
        except re.error:
            return False
    return False


def _text_contains(value: str, query_value: str, *, ignore_case: bool) -> bool:
    left = str(value)
    right = str(query_value)
    if ignore_case:
        left = left.lower()
        right = right.lower()
    return bool(right and right in left)


def _index_source_tables(index: SourceIndex, cfg: Mapping[str, Any]) -> None:
    sources = [config_source("table.include.list")]
    for table_name in _split_csv(cfg.get("table.include.list")):
        values = [table_name]
        parts = [part for part in table_name.split(".") if part]
        if parts:
            values.append(parts[-1])
        _add(index, "tables.source", values, sources)
        if len(parts) >= 2:
            _add(index, "db.schema", [parts[0]], sources)


def _index_sink_tables(
    index: SourceIndex, cfg: Mapping[str, Any], *, facts: Any
) -> None:
    for _topic, table in parse_topic2table_map(cfg.get("topic2TableMap")):
        _add(index, "tables.sink", [table], [config_source("topic2TableMap")])

    for table in facts.sink_tables:
        table_sources = _config_sources(iceberg_facts.table_sources(cfg, table=table))
        _add(index, "tables.sink", [table], table_sources)

    for full_name in facts.sink_table_full_names():
        parsed = iceberg_facts.parse_full_table_name(full_name)
        full_table_sources: Tuple[str, ...] = ()
        if parsed is not None:
            full_table_sources = _config_sources(
                iceberg_facts.table_sources(cfg, table=parsed[1], full_name=full_name)
            )
        if not full_table_sources and facts.sink_database:
            full_table_sources = (config_source("transforms.setTableName.db.name"),)
        _add(index, "tables.sink_full", [full_name], full_table_sources)

    dynamic_sources = _dynamic_table_sources(cfg)
    for table in facts.sink_tables:
        if not index.get("tables.sink", {}).get(table):
            _add(index, "tables.sink", [table], dynamic_sources)
    for full_name in facts.sink_table_full_names():
        if not index.get("tables.sink_full", {}).get(full_name):
            _add(index, "tables.sink_full", [full_name], dynamic_sources)


def _index_topics(index: SourceIndex, cfg: Mapping[str, Any], *, facts: Any) -> None:
    _add_config_key_values(index, "topics.consumed", cfg, ("topics",))

    for topic, _table in parse_topic2table_map(cfg.get("topic2TableMap")):
        _add(index, "topics.consumed", [topic], [config_source("topic2TableMap")])

    _add_config_key_values(index, "topics.produced", cfg, ("topic",))

    topic_prefix = cfg.get("topic.prefix")
    if topic_prefix:
        _add(
            index,
            "topics.pattern",
            [facts.produced_pattern],
            [config_source("topic.prefix")],
        )

    _add_config_key_values(index, "topics.pattern", cfg, ("topics.regex",))

    for pattern in facts.topic_patterns():
        route_sources = _config_sources(
            iceberg_facts.route_regex_sources_for_pattern(cfg, pattern)
        )
        _add(index, "topics.pattern", [pattern], route_sources)


def _add_config_key_values(
    index: SourceIndex, field: str, cfg: Mapping[str, Any], keys: Iterable[str]
) -> None:
    for key in keys:
        _add(index, field, _split_csv(cfg.get(key)), [config_source(key)])


def _dynamic_table_sources(cfg: Mapping[str, Any]) -> Tuple[str, ...]:
    keys = [
        "topics",
        "topics.regex",
        "transforms.setTableName.table.suffix",
        "transforms.setTableName.db.name",
    ]
    return _dedupe(config_source(key) for key in keys if cfg.get(key) is not None)


def _config_sources(keys: Iterable[str]) -> Tuple[str, ...]:
    return _dedupe(config_source(key) for key in keys)


def _add(
    index: SourceIndex, field: str, values: Iterable[Any], sources: Iterable[str]
) -> None:
    clean_sources = _dedupe(sources)
    if not clean_sources:
        return
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        field_map = index.setdefault(field, {})
        field_map[text] = _dedupe([*field_map.get(text, ()), *clean_sources])


def _split_csv(raw: Any) -> list[str]:
    value = str(raw or "").strip()
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _dedupe(values: Iterable[str]) -> Tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value).strip()))
