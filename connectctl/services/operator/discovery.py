from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from ...app.context import CliContext
from ...exceptions import ConfigError
from ...logging_utils import get_logger
from ...models import Environment
from ..connector_facts import ConnectorFacts
from ..search.evaluator import SearchEvaluator
from ..search.models import (
    SearchAnd,
    SearchExplainMode,
    SearchExpression,
    SearchFieldRef,
    SearchLeaf,
    SearchMatchDetail,
    SearchOperator,
    SearchOr,
    SearchQuery,
    SearchResultItem,
    SearchSource,
    SearchView,
)
from ..search.sources import collect_live_facts, collect_repo_facts

_ALL_ENVS = ("dev", "stage", "prod")


@dataclass(frozen=True)
class DiscoveryOptions:
    """Scope and matching options shared by operator commands."""

    source: SearchSource = SearchSource.repo
    envs: Tuple[str, ...] = _ALL_ENVS
    cluster_filter: Optional[str] = None
    ignore_case: bool = False
    limit: Optional[int] = 50
    kind: str = "auto"

    @classmethod
    def from_args(
        cls,
        args: Any,
        *,
        default_source: SearchSource = SearchSource.repo,
        default_limit: Optional[int] = 50,
    ) -> "DiscoveryOptions":
        raw_source = str(
            getattr(args, "source", default_source.value) or default_source.value
        )
        source = SearchSource(raw_source)
        envs = parse_envs(str(getattr(args, "env", "all") or "all"))
        cluster_filter = parse_cluster_filter(
            str(getattr(args, "cluster", "all") or "all")
        )
        return cls(
            source=source,
            envs=envs,
            cluster_filter=cluster_filter,
            ignore_case=bool(getattr(args, "ignore_case", False)),
            limit=getattr(args, "limit", default_limit),
            kind=str(getattr(args, "kind", "auto") or "auto"),
        )


@dataclass(frozen=True)
class DiscoveryRunResult:
    """Resolved facts and matches for one user object."""

    query_object: str
    object_kind: str
    options: DiscoveryOptions
    results: Tuple[SearchResultItem, ...] = ()
    facts: Tuple[ConnectorFacts, ...] = ()
    warnings: Tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.query_object,
            "object_kind": self.object_kind,
            "source": self.options.source.value,
            "env": list(self.options.envs),
            "cluster": self.options.cluster_filter or "all",
            "count": len(self.results),
            "results": [
                item.to_dict(explain=SearchExplainMode.long) for item in self.results
            ],
            "warnings": list(self.warnings),
        }


class DiscoveryService:
    """Shared object resolver used by operator commands.

    The implementation deliberately reuses the existing search facts and evaluator.
    BKKT therefore has one source of truth for "where this connector/topic/table
    appears" instead of one custom index per command.
    """

    def __init__(self, *, ctx: CliContext, logger: Optional[logging.Logger] = None):
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)

    def resolve(
        self, obj: str, *, options: DiscoveryOptions, args: Any
    ) -> DiscoveryRunResult:
        query_object = str(obj or "").strip()
        if not query_object:
            raise ConfigError("Object to explain/search must be non-empty")
        self._validate_cluster(options)
        object_kind = infer_object_kind(query_object, explicit=options.kind)
        expression = build_object_expression(query_object, kind=object_kind)
        live_candidate_names = (query_object,) if object_kind == "connector" else ()
        facts, warnings = self.collect_facts(
            options=options,
            args=args,
            expression=expression,
            live_candidate_names=live_candidate_names,
        )
        evaluator = SearchEvaluator(ignore_case=options.ignore_case)
        results: List[SearchResultItem] = []
        for facts_item in facts:
            evaluated = evaluator.evaluate(expression, facts=facts_item)
            if evaluated.matched:
                results.append(
                    SearchResultItem(facts=facts_item, matched=evaluated.details)
                )
        results.sort(key=_sort_result)
        if options.limit is not None:
            results = results[: int(options.limit)]
        return DiscoveryRunResult(
            query_object=query_object,
            object_kind=object_kind,
            options=options,
            results=tuple(results),
            facts=tuple(facts),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def collect_facts(
        self,
        *,
        options: DiscoveryOptions,
        args: Any,
        expression: SearchExpression | None = None,
        live_candidate_names: Tuple[str, ...] = (),
    ) -> Tuple[List[ConnectorFacts], List[str]]:
        query = SearchQuery(
            source=options.source,
            envs=options.envs,
            cluster_filter=options.cluster_filter,
            view=SearchView.long,
            explain=SearchExplainMode.long,
            limit=None,
            ignore_case=options.ignore_case,
            expression=expression or SearchAnd(items=()),
            live_candidate_names=live_candidate_names,
        )
        facts: List[ConnectorFacts] = []
        warnings: List[str] = []
        if options.source in {SearchSource.repo, SearchSource.both}:
            repo_facts, repo_warnings = collect_repo_facts(
                ctx=self.ctx, query=query, args=args, logger=self.log
            )
            facts.extend(repo_facts)
            warnings.extend(repo_warnings)
        if options.source in {SearchSource.live, SearchSource.both}:
            live_facts, live_warnings = collect_live_facts(
                ctx=self.ctx, query=query, args=args, logger=self.log
            )
            facts.extend(live_facts)
            warnings.extend(live_warnings)
        return facts, list(dict.fromkeys(warnings))

    def _validate_cluster(self, options: DiscoveryOptions) -> None:
        if (
            options.cluster_filter
            and options.cluster_filter not in self.ctx.settings.cluster_groups
        ):
            raise ConfigError(
                f"Unknown cluster group: {options.cluster_filter!r}. "
                f"Expected one of: {', '.join(sorted(self.ctx.settings.cluster_groups)) or '<none>'}"
            )


def parse_envs(raw: str) -> Tuple[str, ...]:
    value = raw.strip().lower()
    if not value or value == "all":
        return _ALL_ENVS
    envs = tuple(
        dict.fromkeys(part.strip().lower() for part in value.split(",") if part.strip())
    )
    for env in envs:
        Environment.from_str(env)
    return envs


def parse_cluster_filter(raw: str) -> Optional[str]:
    value = raw.strip()
    return None if not value or value == "all" else value


def infer_object_kind(obj: str, *, explicit: str = "auto") -> str:
    explicit = explicit.strip().lower()
    if explicit and explicit != "auto":
        return explicit
    if obj.startswith("re:"):
        return "regex"
    if obj.startswith("/") and obj.endswith("/") and len(obj) > 2:
        return "regex"
    if obj.startswith("prod__") or obj.startswith("stage__") or obj.startswith("dev__"):
        return "table"
    if "." in obj and any(marker in obj for marker in ("__raw", "__ods", "__events")):
        return "table"
    if "." in obj and obj.count(".") >= 3 and (".source." in obj or ".sink." in obj):
        return "connector"
    if "." in obj:
        return "topic_or_table"
    return "object"


def normalize_regex_object(obj: str) -> str:
    if obj.startswith("re:"):
        return obj[3:]
    if obj.startswith("/") and obj.endswith("/") and len(obj) > 2:
        return obj[1:-1]
    return obj


def build_object_expression(obj: str, *, kind: str) -> SearchOr:
    pattern = normalize_regex_object(obj)
    if kind == "regex":
        return SearchOr(
            items=tuple(
                SearchLeaf(
                    fields=(SearchFieldRef(field),),
                    operator=SearchOperator.regex,
                    values=(pattern,),
                )
                for field in _TEXT_FIELDS
            )
        )

    exact_fields = (
        "name",
        "topics.any",
        "topics.pattern",
        "tables.source",
        "tables.sink",
        "tables.sink_full",
        "db.name",
        "db.schema",
        "db.server",
        "sink.database",
        "domain",
        "dataset",
        "path",
    )
    leaves: list[SearchLeaf] = [
        SearchLeaf(
            fields=tuple(SearchFieldRef(field) for field in exact_fields),
            operator=SearchOperator.eq,
            values=(obj,),
        ),
        SearchLeaf(
            fields=(SearchFieldRef("name"),),
            operator=SearchOperator.fuzzy,
            values=(obj,),
        ),
    ]
    if _looks_like_safe_regex(obj):
        leaves.append(
            SearchLeaf(
                fields=tuple(SearchFieldRef(field) for field in _TEXT_FIELDS),
                operator=SearchOperator.regex,
                values=(obj,),
            )
        )
    return SearchOr(items=tuple(leaves))


def facts_topics(facts: ConnectorFacts) -> Tuple[str, ...]:
    return _dedupe(
        [
            *facts.consumed_topics,
            *facts.produced_topics,
            *facts.topic_patterns(),
        ]
    )


def facts_tables(facts: ConnectorFacts) -> Tuple[str, ...]:
    return _dedupe(
        [
            *facts.source_tables,
            *facts.sink_tables,
            *facts.sink_table_full_names(),
        ]
    )


def related_facts(
    seed: Sequence[SearchResultItem], all_facts: Sequence[ConnectorFacts]
) -> Tuple[ConnectorFacts, ...]:
    seed_names = {item.facts.name for item in seed}
    seed_topics = {v for item in seed for v in facts_topics(item.facts)}
    seed_tables = {v for item in seed for v in facts_tables(item.facts)}
    related: list[ConnectorFacts] = []
    for facts in all_facts:
        if facts.name in seed_names:
            related.append(facts)
            continue
        if seed_topics.intersection(facts_topics(facts)):
            related.append(facts)
            continue
        if seed_tables.intersection(facts_tables(facts)):
            related.append(facts)
    related.sort(
        key=lambda facts: (
            facts.origin,
            ",".join(facts.envs),
            ",".join(facts.clusters),
            facts.name,
        )
    )
    return tuple(related)


def summarize_match_fields(details: Iterable[SearchMatchDetail]) -> Tuple[str, ...]:
    return _dedupe(detail.field for detail in details)


def _looks_like_safe_regex(value: str) -> bool:
    if not any(ch in value for ch in "^$*+?[]()|\\"):
        return False
    try:
        re.compile(value)
    except re.error:
        return False
    return True


def _sort_result(item: SearchResultItem) -> tuple[str, str, str, str, str]:
    facts = item.facts
    return (
        facts.origin,
        ",".join(facts.envs),
        ",".join(facts.clusters),
        facts.name,
        facts.path or "",
    )


def _dedupe(values: Iterable[Any]) -> Tuple[str, ...]:
    return tuple(dict.fromkeys(str(v).strip() for v in values if str(v or "").strip()))


_TEXT_FIELDS = (
    "name",
    "path",
    "topics.any",
    "topics.pattern",
    "tables.source",
    "tables.sink",
    "tables.sink_full",
    "db.host",
    "db.name",
    "db.schema",
    "db.server",
    "sink.database",
    "domain",
    "dataset",
    "system",
)


__all__ = [
    "DiscoveryOptions",
    "DiscoveryRunResult",
    "DiscoveryService",
    "build_object_expression",
    "facts_tables",
    "facts_topics",
    "infer_object_kind",
    "parse_cluster_filter",
    "parse_envs",
    "related_facts",
    "summarize_match_fields",
]
