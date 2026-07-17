from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Tuple

ICEBERG_TABLE_KEY_PREFIX = "iceberg.table."
ICEBERG_TABLES_KEY = "iceberg.tables"
ICEBERG_ROUTE_REGEX_SUFFIX = "route-regex"


def split_csv(raw: Any) -> list[str]:
    value = str(raw or "").strip()
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def normalize_values(values: Iterable[Any]) -> Tuple[str, ...]:
    normalized = {
        str(value).strip()
        for value in values
        if value is not None and str(value).strip()
    }
    return tuple(sorted(normalized))


def parse_full_table_name(raw: Any) -> Optional[Tuple[Optional[str], str]]:
    text = str(raw or "").strip()
    if not text:
        return None
    if "." not in text:
        return None, text
    namespace, table = text.rsplit(".", 1)
    namespace = namespace.strip()
    table = table.strip()
    if not table:
        return None
    return (namespace or None), table


def format_full_table_name(database: Optional[str], table: str) -> str:
    return f"{database}.{table}" if database else table


def parse_table_config_key(key: Any) -> Optional[Tuple[Optional[str], str, str]]:
    text = str(key or "").strip()
    if not text.startswith(ICEBERG_TABLE_KEY_PREFIX):
        return None
    body = text[len(ICEBERG_TABLE_KEY_PREFIX) :]
    if "." not in body:
        return None
    table_name, prop = body.rsplit(".", 1)
    parsed = parse_full_table_name(table_name)
    if parsed is None:
        return None
    database, table = parsed
    prop = prop.strip()
    if not prop:
        return None
    return database, table, prop


def iter_tables_from_config(
    cfg: Mapping[str, Any],
) -> Iterable[Tuple[Optional[str], str, str]]:
    for raw_table in split_csv(cfg.get(ICEBERG_TABLES_KEY)):
        parsed_full_name = parse_full_table_name(raw_table)
        if parsed_full_name is not None:
            database, table = parsed_full_name
            yield database, table, ICEBERG_TABLES_KEY

    for key, value in cfg.items():
        if value is None:
            continue
        parsed_config_key = parse_table_config_key(key)
        if parsed_config_key is None:
            continue
        database, table, _prop = parsed_config_key
        yield database, table, str(key)


def extract_databases_from_config(cfg: Mapping[str, Any]) -> Tuple[str, ...]:
    return normalize_values(
        database
        for database, _table, _source in iter_tables_from_config(cfg)
        if database
    )


def extract_tables_from_config(cfg: Mapping[str, Any]) -> Tuple[str, ...]:
    return normalize_values(
        table for _database, table, _source in iter_tables_from_config(cfg)
    )


def extract_full_table_names_from_config(cfg: Mapping[str, Any]) -> Tuple[str, ...]:
    return normalize_values(
        format_full_table_name(database, table)
        for database, table, _source in iter_tables_from_config(cfg)
        if database
    )


def extract_route_regex_patterns_from_config(cfg: Mapping[str, Any]) -> Tuple[str, ...]:
    patterns: list[str] = []
    for key, value in cfg.items():
        if value is None:
            continue
        parsed = parse_table_config_key(key)
        if parsed is None:
            continue
        _database, _table, prop = parsed
        if prop != ICEBERG_ROUTE_REGEX_SUFFIX:
            continue
        pattern = str(value).strip()
        if pattern:
            patterns.append(pattern)
    return normalize_values(patterns)


def route_regex_sources_for_pattern(
    cfg: Mapping[str, Any], pattern: str
) -> Tuple[str, ...]:
    sources: list[str] = []
    for key, value in cfg.items():
        if value is None or str(value).strip() != pattern:
            continue
        parsed = parse_table_config_key(key)
        if parsed is None:
            continue
        _database, _table, prop = parsed
        if prop == ICEBERG_ROUTE_REGEX_SUFFIX:
            sources.append(str(key))
    return normalize_values(sources)


def table_sources(
    cfg: Mapping[str, Any], *, table: str, full_name: Optional[str] = None
) -> Tuple[str, ...]:
    sources: list[str] = []
    for database, candidate_table, source in iter_tables_from_config(cfg):
        if candidate_table == table:
            sources.append(source)
        if full_name and format_full_table_name(database, candidate_table) == full_name:
            sources.append(source)
    return normalize_values(sources)
