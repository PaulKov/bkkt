from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ..iceberg import extract_iceberg_glue_bootstrap
from ..kafka.topics import infer_topics, infer_topics_from_config
from ..models import ConnectorManifest
from . import connector_facts_iceberg as iceberg_facts
from .connector_name_meta import ConnectorNameMeta, parse_connector_name_meta

_TOPIC_TRAILING_MARKERS = {"dbt", "changes"}


def _first_non_empty(cfg: Mapping[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = cfg.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _split_csv(raw: Any) -> List[str]:
    value = str(raw or "").strip()
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _normalize_values(values: Iterable[Any]) -> Tuple[str, ...]:
    normalized = {
        str(value).strip()
        for value in values
        if value is not None and str(value).strip()
    }
    return tuple(sorted(normalized))


def extract_source_tables_from_config(cfg: Mapping[str, Any]) -> List[str]:
    return _split_csv(cfg.get("table.include.list"))


def extract_source_table_search_values_from_config(
    cfg: Mapping[str, Any],
) -> Tuple[str, ...]:
    values: list[str] = []
    for table_name in extract_source_tables_from_config(cfg):
        values.append(table_name)
        parts = [part for part in table_name.split(".") if part]
        if parts:
            values.append(parts[-1])
    return _normalize_values(values)


def extract_sink_databases_from_config(cfg: Mapping[str, Any]) -> Tuple[str, ...]:
    values: List[str] = []
    explicit = _first_non_empty(
        cfg,
        "transforms.setTableName.db.name",
        "iceberg.db_name",
        "iceberg.db.name",
        "iceberg.tables.default-namespace",
        "database",
        "database.name",
    )
    if explicit:
        values.extend(_split_csv(explicit))
    values.extend(iceberg_facts.extract_databases_from_config(cfg))
    return _normalize_values(values)


def extract_sink_database_from_config(cfg: Mapping[str, Any]) -> Optional[str]:
    databases = extract_sink_databases_from_config(cfg)
    return databases[0] if databases else None


def extract_sink_warehouse_from_config(cfg: Mapping[str, Any]) -> Optional[str]:
    return _first_non_empty(
        cfg,
        "iceberg.catalog.glue.warehouse",
        "iceberg.catalog.warehouse",
        "iceberg.warehouse",
    )


def extract_sink_tables_from_config(cfg: Mapping[str, Any]) -> List[str]:
    tables: set[str] = set()
    for _topic, table in parse_topic2table_map(cfg.get("topic2TableMap")):
        tables.add(table)

    tables.update(iceberg_facts.extract_tables_from_config(cfg))

    dynamic_tables = _infer_dynamic_sink_tables_from_topics(cfg)
    tables.update(dynamic_tables)

    return sorted(tables)


def extract_sink_table_full_names_from_config(
    cfg: Mapping[str, Any],
) -> Tuple[str, ...]:
    return iceberg_facts.extract_full_table_names_from_config(cfg)


def extract_topic_patterns_from_config(cfg: Mapping[str, Any]) -> Tuple[str, ...]:
    patterns: List[str] = []
    topic_regex = cfg.get("topics.regex")
    if topic_regex is not None and str(topic_regex).strip():
        patterns.append(str(topic_regex).strip())

    patterns.extend(iceberg_facts.extract_route_regex_patterns_from_config(cfg))

    return _normalize_values(patterns)


def extract_topic_table_pairs_from_config(
    cfg: Mapping[str, Any],
) -> List[Tuple[str, str]]:
    explicit = parse_topic2table_map(cfg.get("topic2TableMap"))
    if explicit:
        return explicit

    topics = infer_topics_from_config(dict(cfg)).consumed_topics or []
    if not topics:
        return []

    pairs: set[Tuple[str, str]] = set()
    for key, value in cfg.items():
        if value is None:
            continue
        parsed = iceberg_facts.parse_table_config_key(key)
        if parsed is None:
            continue
        _database, table, prop = parsed
        if prop != "route-regex":
            continue
        try:
            rx = re.compile(str(value))
        except re.error:
            continue
        for topic in topics:
            if rx.search(topic):
                pairs.add((topic, table))

    if pairs:
        return sorted(pairs)

    dynamic_pairs = _infer_dynamic_topic_table_pairs(cfg, topics)
    if dynamic_pairs:
        return dynamic_pairs

    return []


def parse_topic2table_map(raw: Any) -> List[Tuple[str, str]]:
    mappings: List[Tuple[str, str]] = []
    for item in _split_csv(raw):
        if "=" not in item:
            continue
        topic, table = item.split("=", 1)
        topic = topic.strip()
        table = table.strip()
        if topic and table:
            mappings.append((topic, table))
    return mappings


def extract_db_hosts_from_config(cfg: Mapping[str, Any]) -> Tuple[str, ...]:
    return _normalize_values(
        [
            cfg.get("database.hostname"),
            cfg.get("database.host"),
            cfg.get("connection.host"),
        ]
    )


def extract_db_ports_from_config(cfg: Mapping[str, Any]) -> Tuple[str, ...]:
    return _normalize_values(
        [
            cfg.get("database.port"),
            cfg.get("connection.port"),
        ]
    )


def extract_db_names_from_config(cfg: Mapping[str, Any]) -> Tuple[str, ...]:
    values: List[str] = []
    for key in (
        "database.dbname",
        "database.names",
        "database.include.list",
        "database.name",
        "database.db.name",
    ):
        values.extend(_split_csv(cfg.get(key)))
    return _normalize_values(values)


def extract_db_schemas_from_config(cfg: Mapping[str, Any]) -> Tuple[str, ...]:
    values: List[str] = []
    values.extend(_split_csv(cfg.get("schema.include.list")))
    values.extend(_split_csv(cfg.get("database.schema")))
    values.extend(_split_csv(cfg.get("schema")))
    for table_name in extract_source_tables_from_config(cfg):
        parts = [part for part in table_name.split(".") if part]
        if len(parts) >= 2:
            values.append(parts[0])
    return _normalize_values(values)


def extract_db_servers_from_config(cfg: Mapping[str, Any]) -> Tuple[str, ...]:
    values: List[str] = []
    for key in (
        "database.server.name",
        "database.server.id",
        "publication.name",
        "topic.prefix",
    ):
        val = cfg.get(key)
        if val is not None:
            values.append(str(val))
    return _normalize_values(values)


def _infer_dynamic_sink_tables_from_topics(cfg: Mapping[str, Any]) -> List[str]:
    suffix = _extract_table_suffix(cfg)
    if not suffix:
        return []
    topics = infer_topics_from_config(dict(cfg)).consumed_topics or []
    tables = {
        f"{base_table}__{suffix}"
        for topic in topics
        for base_table in [_infer_base_table_from_topic(topic)]
        if base_table
    }
    return sorted(tables)


def _infer_dynamic_topic_table_pairs(
    cfg: Mapping[str, Any], topics: Sequence[str]
) -> List[Tuple[str, str]]:
    suffix = _extract_table_suffix(cfg)
    if not suffix:
        return []
    pairs: List[Tuple[str, str]] = []
    for topic in topics:
        base_table = _infer_base_table_from_topic(topic)
        if base_table:
            pairs.append((topic, f"{base_table}__{suffix}"))
    return sorted(set(pairs))


def _extract_table_suffix(cfg: Mapping[str, Any]) -> Optional[str]:
    value = cfg.get("transforms.setTableName.table.suffix")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _infer_base_table_from_topic(topic: str) -> Optional[str]:
    tokens = [part.strip() for part in str(topic or "").split(".") if part.strip()]
    if not tokens:
        return None
    while tokens and tokens[-1].isdigit():
        tokens.pop()
    while tokens and tokens[-1].lower() in _TOPIC_TRAILING_MARKERS:
        tokens.pop()
    if not tokens:
        return None
    return tokens[-1]


@dataclass(frozen=True)
class ConnectorScopeAlias:
    env: str
    cluster: str
    urls: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "env": self.env,
            "cluster": self.cluster,
            "urls": list(self.urls),
        }


@dataclass(frozen=True)
class ConnectorFacts:
    name: str
    origin: str
    path: Optional[str]
    envs: Tuple[str, ...]
    clusters: Tuple[str, ...]
    alias_scopes: Tuple[ConnectorScopeAlias, ...]
    domain: Optional[str]
    dataset: Optional[str]
    connector_type: Optional[str]
    system: Optional[str]
    layer: Optional[str]
    mode: Optional[str]
    kind: Optional[str]
    source_tables: Tuple[str, ...]
    sink_tables: Tuple[str, ...]
    consumed_topics: Tuple[str, ...]
    produced_topics: Tuple[str, ...]
    produced_pattern: Optional[str]
    db_hosts: Tuple[str, ...]
    db_ports: Tuple[str, ...]
    db_names: Tuple[str, ...]
    db_schemas: Tuple[str, ...]
    db_servers: Tuple[str, ...]
    sink_database: Optional[str]
    sink_warehouse: Optional[str]
    config: Dict[str, Any]

    def sink_table_full_names(self) -> Tuple[str, ...]:
        explicit_full_names = list(
            extract_sink_table_full_names_from_config(self.config)
        )
        if self.sink_database:
            explicit_full_names.extend(
                f"{self.sink_database}.{table}" for table in self.sink_tables
            )
        return _normalize_values(explicit_full_names)

    def sink_database_names(self) -> Tuple[str, ...]:
        return _normalize_values(
            [self.sink_database] + list(extract_sink_databases_from_config(self.config))
        )

    def topic_patterns(self) -> Tuple[str, ...]:
        return _normalize_values(
            list(extract_topic_patterns_from_config(self.config))
            + ([self.produced_pattern] if self.produced_pattern else [])
        )

    def query_fields(self) -> Dict[str, Tuple[str, ...]]:
        topic_patterns = self.topic_patterns()
        fields: Dict[str, Tuple[str, ...]] = {
            "name": (self.name,),
            "origin": (self.origin,),
            "env": self.envs,
            "cluster": self.clusters,
            "tables.source": extract_source_table_search_values_from_config(
                self.config
            ),
            "tables.sink": self.sink_tables,
            "tables.sink_full": self.sink_table_full_names(),
            "topics.consumed": self.consumed_topics,
            "topics.produced": self.produced_topics,
            "topics.pattern": topic_patterns,
            "topics.any": _normalize_values(
                list(self.consumed_topics)
                + list(self.produced_topics)
                + list(topic_patterns)
            ),
            "db.host": self.db_hosts,
            "db.port": self.db_ports,
            "db.name": self.db_names,
            "db.schema": self.db_schemas,
            "db.server": self.db_servers,
        }
        if self.path:
            fields["path"] = (self.path,)
        if self.domain:
            fields["domain"] = (self.domain,)
        if self.dataset:
            fields["dataset"] = (self.dataset,)
        if self.connector_type:
            fields["type"] = (self.connector_type,)
        if self.system:
            fields["system"] = (self.system,)
        if self.layer:
            fields["layer"] = (self.layer,)
        if self.mode:
            fields["mode"] = (self.mode,)
        if self.kind:
            fields["kind"] = (self.kind,)
        sink_databases = self.sink_database_names()
        if sink_databases:
            fields["sink.database"] = sink_databases
        if self.sink_warehouse:
            fields["sink.warehouse"] = (self.sink_warehouse,)
        return fields

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "origin": self.origin,
            "path": self.path,
            "env": list(self.envs),
            "cluster": list(self.clusters),
            "alias_scopes": [alias.to_dict() for alias in self.alias_scopes],
            "domain": self.domain,
            "dataset": self.dataset,
            "type": self.connector_type,
            "system": self.system,
            "layer": self.layer,
            "mode": self.mode,
            "kind": self.kind,
            "tables": {
                "source": list(self.source_tables),
                "sink": list(self.sink_tables),
                "sink_full": list(self.sink_table_full_names()),
            },
            "topics": {
                "consumed": list(self.consumed_topics),
                "produced": list(self.produced_topics),
                "produced_pattern": self.produced_pattern,
                "patterns": list(self.topic_patterns()),
                "any": list(self.query_fields().get("topics.any", ())),
            },
            "db": {
                "host": list(self.db_hosts),
                "port": list(self.db_ports),
                "name": list(self.db_names),
                "schema": list(self.db_schemas),
                "server": list(self.db_servers),
            },
            "sink": {
                "database": self.sink_database,
                "warehouse": self.sink_warehouse,
            },
            "config": self.config,
        }


def build_connector_facts_from_manifest(
    manifest: ConnectorManifest,
    *,
    origin: str,
    path: Optional[str],
    envs: Sequence[str],
    clusters: Sequence[str],
    alias_scopes: Sequence[ConnectorScopeAlias] = (),
) -> ConnectorFacts:
    meta = parse_connector_name_meta(manifest.name)
    cfg = dict(manifest.config)
    topics = infer_topics(manifest)
    bootstrap = extract_iceberg_glue_bootstrap(manifest)
    sink_database = extract_sink_database_from_config(cfg)
    sink_warehouse = extract_sink_warehouse_from_config(cfg)
    if bootstrap:
        sink_database = sink_database or bootstrap.db_name
        sink_warehouse = sink_warehouse or bootstrap.location_uri
    return _build_connector_facts(
        name=manifest.name,
        origin=origin,
        path=path,
        envs=envs,
        clusters=clusters,
        alias_scopes=alias_scopes,
        meta=meta,
        cfg=cfg,
        topics=topics,
        sink_database=sink_database,
        sink_warehouse=sink_warehouse,
    )


def build_connector_facts_from_live_config(
    *,
    name: str,
    cfg: Mapping[str, Any],
    envs: Sequence[str],
    clusters: Sequence[str],
    alias_scopes: Sequence[ConnectorScopeAlias],
) -> ConnectorFacts:
    meta = parse_connector_name_meta(name)
    topics = infer_topics_from_config(dict(cfg))
    return _build_connector_facts(
        name=name,
        origin="live",
        path=None,
        envs=envs,
        clusters=clusters,
        alias_scopes=alias_scopes,
        meta=meta,
        cfg=dict(cfg),
        topics=topics,
        sink_database=extract_sink_database_from_config(cfg),
        sink_warehouse=extract_sink_warehouse_from_config(cfg),
    )


def _build_connector_facts(
    *,
    name: str,
    origin: str,
    path: Optional[str],
    envs: Sequence[str],
    clusters: Sequence[str],
    alias_scopes: Sequence[ConnectorScopeAlias],
    meta: ConnectorNameMeta,
    cfg: Dict[str, Any],
    topics,
    sink_database: Optional[str],
    sink_warehouse: Optional[str],
) -> ConnectorFacts:
    return ConnectorFacts(
        name=name,
        origin=origin,
        path=path,
        envs=_normalize_values(envs or ([meta.env] if meta.env else [])),
        clusters=_normalize_values(clusters),
        alias_scopes=tuple(alias_scopes),
        domain=meta.domain,
        dataset=meta.dataset,
        connector_type=meta.integration_type,
        system=meta.system,
        layer=meta.layer,
        mode=meta.source_mode,
        kind=meta.sink_kind,
        source_tables=_normalize_values(extract_source_tables_from_config(cfg)),
        sink_tables=_normalize_values(extract_sink_tables_from_config(cfg)),
        consumed_topics=_normalize_values(topics.consumed_topics or ()),
        produced_topics=_normalize_values(topics.produced_topics or ()),
        produced_pattern=(
            str(topics.produced_pattern).strip() if topics.produced_pattern else None
        ),
        db_hosts=extract_db_hosts_from_config(cfg),
        db_ports=extract_db_ports_from_config(cfg),
        db_names=extract_db_names_from_config(cfg),
        db_schemas=extract_db_schemas_from_config(cfg),
        db_servers=extract_db_servers_from_config(cfg),
        sink_database=sink_database,
        sink_warehouse=sink_warehouse,
        config=cfg,
    )


__all__ = [
    "ConnectorFacts",
    "ConnectorScopeAlias",
    "build_connector_facts_from_live_config",
    "build_connector_facts_from_manifest",
    "extract_db_hosts_from_config",
    "extract_db_names_from_config",
    "extract_db_ports_from_config",
    "extract_db_schemas_from_config",
    "extract_db_servers_from_config",
    "extract_sink_database_from_config",
    "extract_sink_databases_from_config",
    "extract_sink_tables_from_config",
    "extract_sink_table_full_names_from_config",
    "extract_sink_warehouse_from_config",
    "extract_source_table_search_values_from_config",
    "extract_source_tables_from_config",
    "extract_topic_patterns_from_config",
    "extract_topic_table_pairs_from_config",
    "parse_topic2table_map",
]
