from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..connector_facts import ConnectorFacts


class SearchSource(str, Enum):
    repo = "repo"
    live = "live"
    both = "both"


class SearchView(str, Enum):
    short = "short"
    long = "long"


class SearchExplainMode(str, Enum):
    long = "long"
    stats = "stats"
    none = "none"


class SearchMatchMode(str, Enum):
    any = "any"
    all = "all"


class SearchOperator(str, Enum):
    eq = "="
    ne = "!="
    prefix = "^="
    suffix = "$="
    regex = "~="
    fuzzy = "fuzzy"
    exists = "exists"
    missing = "missing"


@dataclass(frozen=True)
class SearchFieldRef:
    name: str
    is_config: bool = False

    def display(self) -> str:
        return f'config("{self.name}")' if self.is_config else self.name


class SearchExpression:
    pass


@dataclass(frozen=True)
class SearchLeaf(SearchExpression):
    fields: Tuple[SearchFieldRef, ...]
    operator: SearchOperator
    values: Tuple[str, ...] = ()
    match_mode: SearchMatchMode = SearchMatchMode.any


@dataclass(frozen=True)
class SearchAnd(SearchExpression):
    items: Tuple[SearchExpression, ...]


@dataclass(frozen=True)
class SearchOr(SearchExpression):
    items: Tuple[SearchExpression, ...]


@dataclass(frozen=True)
class SearchNot(SearchExpression):
    item: SearchExpression


@dataclass(frozen=True)
class SearchOccurrence:
    field: str
    value: str
    sources: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "value": self.value,
            "sources": list(self.sources),
        }


@dataclass(frozen=True)
class SearchMatchDetail:
    field: str
    operator: str
    query_value: Optional[str]
    matched_values: Tuple[str, ...] = ()
    sources: Tuple[str, ...] = ()
    occurrences: Tuple[SearchOccurrence, ...] = ()

    def to_dict(self, *, include_explain: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "field": self.field,
            "operator": self.operator,
            "query_value": self.query_value,
            "matched_values": list(self.matched_values),
        }
        if include_explain:
            payload["sources"] = list(self.sources)
            payload["occurrences"] = [item.to_dict() for item in self.occurrences]
        return payload


@dataclass(frozen=True)
class SearchResultItem:
    facts: ConnectorFacts
    matched: Tuple[SearchMatchDetail, ...]

    def to_dict(
        self, *, explain: SearchExplainMode = SearchExplainMode.long
    ) -> Dict[str, Any]:
        payload = self.facts.to_dict()
        payload["matched"] = [
            item.to_dict(include_explain=explain == SearchExplainMode.long)
            for item in self.matched
        ]
        return payload


@dataclass(frozen=True)
class SearchQuery:
    source: SearchSource
    envs: Tuple[str, ...]
    cluster_filter: Optional[str]
    view: SearchView
    explain: SearchExplainMode
    limit: Optional[int]
    ignore_case: bool
    expression: SearchExpression
    where_clauses: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    live_candidate_names: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source.value,
            "env": list(self.envs),
            "cluster": self.cluster_filter or "all",
            "view": self.view.value,
            "explain": self.explain.value,
            "limit": self.limit,
            "ignore_case": self.ignore_case,
            "where": list(self.where_clauses),
            "warnings": list(self.warnings),
            "live_candidate_names": list(self.live_candidate_names),
        }


@dataclass
class SearchRunResult:
    query: SearchQuery
    results: List[SearchResultItem] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "query": self.query.to_dict(),
            "count": len(self.results),
            "results": [
                item.to_dict(explain=self.query.explain) for item in self.results
            ],
            "warnings": list(dict.fromkeys([*self.query.warnings, *self.warnings])),
        }
        if self.query.explain == SearchExplainMode.stats:
            payload["stats"] = self.stats_to_dict()
        return payload

    def stats_to_dict(self) -> Dict[str, Any]:
        by_env_cluster: Dict[str, int] = {}
        by_config_source: Dict[str, int] = {}
        by_field: Dict[str, int] = {}

        for item in self.results:
            envs = item.facts.envs or ("?",)
            clusters = item.facts.clusters or ("?",)
            for env in envs:
                for cluster in clusters:
                    key = f"{env}/{cluster}"
                    by_env_cluster[key] = by_env_cluster.get(key, 0) + 1
            for match in item.matched:
                by_field[match.field] = by_field.get(match.field, 0) + 1
                for source in match.sources:
                    if source.startswith('config("'):
                        by_config_source[source] = by_config_source.get(source, 0) + 1

        return {
            "by_env_cluster": dict(sorted(by_env_cluster.items())),
            "by_config_source": dict(sorted(by_config_source.items())),
            "by_field": dict(sorted(by_field.items())),
        }


def and_expression(items: Sequence[SearchExpression]) -> SearchExpression:
    flattened: List[SearchExpression] = []
    for item in items:
        if isinstance(item, SearchAnd):
            flattened.extend(item.items)
        else:
            flattened.append(item)
    if not flattened:
        return SearchAnd(items=())
    if len(flattened) == 1:
        return flattened[0]
    return SearchAnd(items=tuple(flattened))


__all__ = [
    "SearchAnd",
    "SearchExpression",
    "SearchExplainMode",
    "SearchFieldRef",
    "SearchLeaf",
    "SearchMatchDetail",
    "SearchMatchMode",
    "SearchNot",
    "SearchOperator",
    "SearchOccurrence",
    "SearchOr",
    "SearchQuery",
    "SearchResultItem",
    "SearchRunResult",
    "SearchSource",
    "SearchView",
    "and_expression",
]
