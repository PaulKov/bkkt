from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import product
from typing import Any, Callable, Iterable, Mapping, Tuple

from ...exceptions import ConfigError

_VAR_RE = re.compile(r"\$\{([^}]+)\}")
_CONFIG_VAR_RE = re.compile(r'^config\(["\'](.+)["\']\)$')
_MAX_EXPANDED_VALUES = 64


@dataclass(frozen=True)
class SearchVariable:
    name: str
    description: str
    resolver: Callable[[Any], Tuple[str, ...]]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description}


def list_search_variables() -> Tuple[SearchVariable, ...]:
    return _VARIABLES


def render_search_variables_text() -> str:
    lines = ["Available search variables:\n"]
    for item in _VARIABLES:
        lines.append(f"- {item.name}: {item.description}\n")
    lines.append('- config("key.with.dots"): config value by exact key\n')
    return "".join(lines)


def expand_value_template(raw: str, *, facts: Any) -> Tuple[str, ...]:
    text = str(raw)
    matches = list(_VAR_RE.finditer(text))
    if not matches:
        return (text,)

    value_sets = [
        _resolve_variable(match.group(1).strip(), facts=facts) for match in matches
    ]
    if any(not values for values in value_sets):
        return ()

    expanded: list[str] = []
    for combo in product(*value_sets):
        candidate = text
        for match, value in zip(matches, combo):
            candidate = candidate.replace(match.group(0), value, 1)
        expanded.append(candidate)
        if len(expanded) >= _MAX_EXPANDED_VALUES:
            break
    return tuple(dict.fromkeys(expanded))


def _resolve_variable(name: str, *, facts: Any) -> Tuple[str, ...]:
    config_match = _CONFIG_VAR_RE.match(name)
    if config_match:
        return _normalize_values(
            [getattr(facts, "config", {}).get(config_match.group(1))]
        )

    resolver = _VARIABLE_MAP.get(name)
    if resolver is None:
        supported = ", ".join(item.name for item in _VARIABLES)
        raise ConfigError(
            f'Unsupported search variable: {name!r}. Supported variables: {supported}, config("key.with.dots")'
        )
    return resolver(facts)


def _field_values(field: str) -> Callable[[Any], Tuple[str, ...]]:
    def _resolver(facts: Any) -> Tuple[str, ...]:
        return tuple(getattr(facts, "query_fields")().get(field, ()))

    return _resolver


def _attr_value(attr: str) -> Callable[[Any], Tuple[str, ...]]:
    def _resolver(facts: Any) -> Tuple[str, ...]:
        return _normalize_values([getattr(facts, attr, None)])

    return _resolver


def _attr_values(attr: str) -> Callable[[Any], Tuple[str, ...]]:
    def _resolver(facts: Any) -> Tuple[str, ...]:
        return _normalize_values(getattr(facts, attr, ()) or ())

    return _resolver


def _connector_index(facts: Any) -> Tuple[str, ...]:
    parts = [part for part in str(getattr(facts, "name", "")).split(".") if part]
    if parts and parts[-1].isdigit():
        return (parts[-1],)
    return ()


def _source_index(facts: Any) -> Tuple[str, ...]:
    if getattr(facts, "connector_type", None) != "source":
        return ()
    return _connector_index(facts)


def _single_topic(facts: Any) -> Tuple[str, ...]:
    values = getattr(facts, "query_fields")().get("topics.any", ())
    return (values[0],) if values else ()


def _normalize_values(values: Iterable[Any]) -> Tuple[str, ...]:
    normalized = {
        str(value).strip()
        for value in values
        if value is not None and str(value).strip()
    }
    return tuple(sorted(normalized))


_VARIABLES: Tuple[SearchVariable, ...] = (
    SearchVariable("connector.name", "connector name", _attr_value("name")),
    SearchVariable("connector.env", "connector environment(s)", _attr_values("envs")),
    SearchVariable(
        "connector.cluster", "resolved cluster group(s)", _attr_values("clusters")
    ),
    SearchVariable(
        "connector.domain", "domain parsed from connector name", _attr_value("domain")
    ),
    SearchVariable(
        "connector.dataset",
        "dataset parsed from connector name",
        _attr_value("dataset"),
    ),
    SearchVariable("connector.type", "source or sink", _attr_value("connector_type")),
    SearchVariable(
        "connector.system", "source/sink system parsed from name", _attr_value("system")
    ),
    SearchVariable(
        "connector.layer", "sink layer parsed from name", _attr_value("layer")
    ),
    SearchVariable(
        "connector.mode", "source mode parsed from name", _attr_value("mode")
    ),
    SearchVariable("connector.kind", "sink kind parsed from name", _attr_value("kind")),
    SearchVariable(
        "connector.index", "final numeric connector index", _connector_index
    ),
    SearchVariable("origin", "repo or live", _attr_value("origin")),
    SearchVariable(
        "path", "repo-relative manifest path when available", _attr_value("path")
    ),
    SearchVariable("env", "alias for connector.env", _attr_values("envs")),
    SearchVariable("cluster", "alias for connector.cluster", _attr_values("clusters")),
    SearchVariable("index", "alias for connector.index", _connector_index),
    SearchVariable(
        "src_index", "final numeric index for source connectors", _source_index
    ),
    SearchVariable(
        "source.database", "source database names", _field_values("db.name")
    ),
    SearchVariable("source.schema", "source schemas", _field_values("db.schema")),
    SearchVariable(
        "source.table", "source table search values", _field_values("tables.source")
    ),
    SearchVariable(
        "source.tables", "source table search values", _field_values("tables.source")
    ),
    SearchVariable("source.host", "source database hosts", _field_values("db.host")),
    SearchVariable("source.port", "source database ports", _field_values("db.port")),
    SearchVariable(
        "source.server",
        "source server/topic prefix identifiers",
        _field_values("db.server"),
    ),
    SearchVariable(
        "sink.database",
        "sink database/namespace values",
        _field_values("sink.database"),
    ),
    SearchVariable("sink.table", "sink table names", _field_values("tables.sink")),
    SearchVariable("sink.tables", "sink table names", _field_values("tables.sink")),
    SearchVariable(
        "sink.full_table",
        "fully-qualified sink table names",
        _field_values("tables.sink_full"),
    ),
    SearchVariable(
        "sink.full_tables",
        "fully-qualified sink table names",
        _field_values("tables.sink_full"),
    ),
    SearchVariable(
        "sink.warehouse", "sink warehouse/location URI", _field_values("sink.warehouse")
    ),
    SearchVariable("topic", "first known topic or topic pattern", _single_topic),
    SearchVariable(
        "topics.consumed", "consumed topic names", _field_values("topics.consumed")
    ),
    SearchVariable(
        "topics.produced", "produced topic names", _field_values("topics.produced")
    ),
    SearchVariable(
        "topics.patterns", "topic regex patterns", _field_values("topics.pattern")
    ),
    SearchVariable(
        "topics.any", "all known topic names and patterns", _field_values("topics.any")
    ),
)

_VARIABLE_MAP: Mapping[str, Callable[[Any], Tuple[str, ...]]] = {
    item.name: item.resolver for item in _VARIABLES
}
