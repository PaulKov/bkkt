from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from ...exceptions import ConfigError
from ...models import Environment
from .models import (
    SearchAnd,
    SearchExpression,
    SearchExplainMode,
    SearchFieldRef,
    SearchLeaf,
    SearchMatchMode,
    SearchNot,
    SearchOperator,
    SearchOr,
    SearchQuery,
    SearchSource,
    SearchView,
    and_expression,
)

_SUPPORTED_FIELDS = {
    "name",
    "origin",
    "env",
    "cluster",
    "domain",
    "dataset",
    "type",
    "system",
    "layer",
    "mode",
    "kind",
    "path",
    "tables.source",
    "tables.sink",
    "tables.sink_full",
    "topics.consumed",
    "topics.produced",
    "topics.pattern",
    "topics.any",
    "db.host",
    "db.port",
    "db.name",
    "db.schema",
    "db.server",
    "sink.database",
    "sink.warehouse",
}


def build_search_query(args) -> SearchQuery:
    source = SearchSource(str(getattr(args, "source", "repo") or "repo").strip())
    envs = _parse_envs(str(getattr(args, "env", "all") or "all").strip().lower())
    cluster_filter = _parse_cluster_filter(
        str(getattr(args, "cluster", "all") or "all")
    )
    view = SearchView(str(getattr(args, "view", "long") or "long").strip())
    explain = SearchExplainMode(str(getattr(args, "explain", "long") or "long").strip())
    limit = getattr(args, "limit", None)
    ignore_case = bool(getattr(args, "ignore_case", False))

    common_exprs = _build_common_flag_predicates(args)
    where_clauses = tuple(
        str(item).strip()
        for item in (getattr(args, "where", []) or [])
        if str(item).strip()
    )
    for clause in where_clauses:
        common_exprs.append(parse_where_clause(clause))

    expression: SearchExpression
    if common_exprs:
        expression = and_expression(common_exprs)
    else:
        expression = SearchAnd(items=())

    return SearchQuery(
        source=source,
        envs=tuple(env.value for env in envs),
        cluster_filter=cluster_filter,
        view=view,
        explain=explain,
        limit=int(limit) if limit else None,
        ignore_case=ignore_case,
        expression=expression,
        where_clauses=where_clauses,
    )


def _parse_envs(raw: str) -> List[Environment]:
    if raw == "all":
        return [Environment.dev, Environment.stage, Environment.prod]
    return [Environment.from_str(raw)]


def _parse_cluster_filter(raw: str) -> Optional[str]:
    text = raw.strip()
    if not text or text.lower() == "all":
        return None
    return text


def _build_common_flag_predicates(args) -> List[SearchExpression]:
    predicates: List[SearchExpression] = []
    predicates.extend(
        _build_value_filter(
            args=args,
            option="name",
            fields=("name",),
        )
    )
    predicates.extend(
        _build_value_filter(
            args=args,
            option="name_prefix",
            fields=("name",),
            operator=SearchOperator.prefix,
        )
    )
    predicates.extend(
        _build_value_filter(
            args=args,
            option="name_suffix",
            fields=("name",),
            operator=SearchOperator.suffix,
        )
    )
    predicates.extend(
        _build_value_filter(
            args=args,
            option="name_regexp",
            fields=("name",),
            operator=SearchOperator.regex,
        )
    )
    predicates.extend(
        _build_value_filter(
            args=args,
            option="name_fuzzy",
            fields=("name",),
            operator=SearchOperator.fuzzy,
        )
    )

    table_mode = SearchMatchMode(str(getattr(args, "table_match", "any") or "any"))
    predicates.extend(
        _build_value_filter(
            args=args,
            option="table",
            fields=("tables.source", "tables.sink", "tables.sink_full"),
            match_mode=table_mode,
        )
    )
    predicates.extend(
        _build_value_filter(
            args=args,
            option="table_prefix",
            fields=("tables.source", "tables.sink", "tables.sink_full"),
            operator=SearchOperator.prefix,
            match_mode=table_mode,
        )
    )
    predicates.extend(
        _build_value_filter(
            args=args,
            option="table_suffix",
            fields=("tables.source", "tables.sink", "tables.sink_full"),
            operator=SearchOperator.suffix,
            match_mode=table_mode,
        )
    )
    predicates.extend(
        _build_value_filter(
            args=args,
            option="table_regexp",
            fields=("tables.source", "tables.sink", "tables.sink_full"),
            operator=SearchOperator.regex,
            match_mode=table_mode,
        )
    )

    topic_mode = SearchMatchMode(str(getattr(args, "topic_match", "any") or "any"))
    predicates.extend(
        _build_value_filter(
            args=args,
            option="topic",
            fields=("topics.any", "topics.pattern"),
            match_mode=topic_mode,
        )
    )
    predicates.extend(
        _build_value_filter(
            args=args,
            option="topic_prefix",
            fields=("topics.any", "topics.pattern"),
            operator=SearchOperator.prefix,
            match_mode=topic_mode,
        )
    )
    predicates.extend(
        _build_value_filter(
            args=args,
            option="topic_suffix",
            fields=("topics.any", "topics.pattern"),
            operator=SearchOperator.suffix,
            match_mode=topic_mode,
        )
    )
    predicates.extend(
        _build_value_filter(
            args=args,
            option="topic_regexp",
            fields=("topics.any", "topics.pattern"),
            operator=SearchOperator.regex,
            match_mode=topic_mode,
        )
    )

    predicates.extend(
        _build_value_filter(args=args, option="domain", fields=("domain",))
    )
    predicates.extend(
        _build_value_filter(args=args, option="dataset", fields=("dataset",))
    )
    predicates.extend(
        _build_value_filter(args=args, option="connector_type", fields=("type",))
    )
    predicates.extend(
        _build_value_filter(args=args, option="system", fields=("system",))
    )
    predicates.extend(_build_value_filter(args=args, option="layer", fields=("layer",)))
    predicates.extend(_build_value_filter(args=args, option="mode", fields=("mode",)))
    predicates.extend(_build_value_filter(args=args, option="kind", fields=("kind",)))
    predicates.extend(
        _build_value_filter(args=args, option="host", fields=("db.host",))
    )
    predicates.extend(
        _build_runtime_config_filter(
            args=args,
            option="kafka_bootstrap",
            keys=(
                "bootstrap.servers",
                "consumer.override.bootstrap.servers",
                "producer.override.bootstrap.servers",
                "schema.history.internal.kafka.bootstrap.servers",
                "iceberg.kafka.bootstrap.servers",
            ),
        )
    )
    predicates.extend(
        _build_runtime_config_filter(
            args=args,
            option="schema_registry_url",
            keys=(
                "schema.registry.url",
                "key.converter.schema.registry.url",
                "value.converter.schema.registry.url",
            ),
        )
    )
    predicates.extend(
        _build_value_filter(
            args=args, option="database", fields=("db.name", "sink.database")
        )
    )
    predicates.extend(
        _build_value_filter(args=args, option="schema", fields=("db.schema",))
    )
    predicates.extend(
        _build_value_filter(args=args, option="server", fields=("db.server",))
    )

    for key in _split_multi_values(getattr(args, "has_config_key", []) or []):
        predicates.append(
            SearchLeaf(
                fields=(SearchFieldRef(name=key, is_config=True),),
                operator=SearchOperator.exists,
            )
        )

    predicates.extend(
        _build_config_filters(getattr(args, "config_eq", []) or [], SearchOperator.eq)
    )
    predicates.extend(
        _build_config_filters(
            getattr(args, "config_prefix", []) or [], SearchOperator.prefix
        )
    )
    predicates.extend(
        _build_config_filters(
            getattr(args, "config_suffix", []) or [], SearchOperator.suffix
        )
    )
    predicates.extend(
        _build_config_filters(
            getattr(args, "config_regexp", []) or [], SearchOperator.regex
        )
    )

    return predicates


def _build_value_filter(
    *,
    args,
    option: str,
    fields: Sequence[str],
    operator: SearchOperator = SearchOperator.eq,
    match_mode: SearchMatchMode = SearchMatchMode.any,
) -> List[SearchExpression]:
    values = _split_multi_values(getattr(args, option, []) or [])
    if not values:
        return []
    return [
        SearchLeaf(
            fields=tuple(SearchFieldRef(name=field_name) for field_name in fields),
            operator=operator,
            values=tuple(values),
            match_mode=match_mode,
        )
    ]


def _build_config_filters(
    entries: Sequence[str], operator: SearchOperator
) -> List[SearchExpression]:
    predicates: List[SearchExpression] = []
    for raw in entries:
        key, value = _split_key_value(raw)
        predicates.append(
            SearchLeaf(
                fields=(SearchFieldRef(name=key, is_config=True),),
                operator=operator,
                values=(value,),
            )
        )
    return predicates


def _build_runtime_config_filter(
    *,
    args,
    option: str,
    keys: Sequence[str],
) -> List[SearchExpression]:
    values = _split_multi_values(getattr(args, option, []) or [])
    if not values:
        return []
    # Regex matching keeps the UX forgiving: host-only input matches full URLs
    # and comma-separated bootstrap lists without adding another contains operator.
    patterns = tuple(re.escape(value) for value in values)
    return [
        SearchLeaf(
            fields=tuple(SearchFieldRef(name=key, is_config=True) for key in keys),
            operator=SearchOperator.regex,
            values=patterns,
            match_mode=SearchMatchMode.all,
        )
    ]


def _split_multi_values(values: Sequence[str]) -> List[str]:
    result: List[str] = []
    for raw in values:
        for item in str(raw or "").split(","):
            value = item.strip()
            if value:
                result.append(value)
    return result


def _split_key_value(raw: str) -> Tuple[str, str]:
    if "=" not in str(raw):
        raise ConfigError(f"Expected KEY=VALUE, got: {raw!r}")
    key, value = str(raw).split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key or not value:
        raise ConfigError(f"Expected non-empty KEY=VALUE, got: {raw!r}")
    return key, value


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str


def parse_where_clause(raw: str) -> SearchExpression:
    tokens = _tokenize(raw)
    parser = _WhereParser(tokens)
    expr = parser.parse_expression()
    parser.expect_eof()
    return expr


def _tokenize(text: str) -> List[_Token]:
    tokens: List[_Token] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch in "()":
            tokens.append(_Token(kind=ch, value=ch))
            i += 1
            continue
        op = _match_operator(text, i)
        if op:
            tokens.append(_Token(kind="OP", value=op))
            i += len(op)
            continue
        if ch in {'"', "'"}:
            value, end = _read_string(text, i)
            tokens.append(_Token(kind="STRING", value=value))
            i = end
            continue
        start = i
        while i < len(text):
            if text[i].isspace() or text[i] in "()":
                break
            if _match_operator(text, i):
                break
            i += 1
        tokens.append(_Token(kind="ATOM", value=text[start:i]))
    return tokens


def _match_operator(text: str, idx: int) -> Optional[str]:
    for op in ("!=", "^=", "$=", "~=", "="):
        if text.startswith(op, idx):
            return op
    return None


def _read_string(text: str, idx: int) -> Tuple[str, int]:
    quote = text[idx]
    idx += 1
    chars: List[str] = []
    while idx < len(text):
        ch = text[idx]
        if ch == "\\" and idx + 1 < len(text):
            chars.append(text[idx + 1])
            idx += 2
            continue
        if ch == quote:
            return "".join(chars), idx + 1
        chars.append(ch)
        idx += 1
    raise ConfigError("Unterminated string in --where expression")


class _WhereParser:
    def __init__(self, tokens: Sequence[_Token]) -> None:
        self.tokens = list(tokens)
        self.pos = 0

    def parse_expression(self) -> SearchExpression:
        return self.parse_or()

    def parse_or(self) -> SearchExpression:
        items = [self.parse_and()]
        while self._match_keyword("OR"):
            items.append(self.parse_and())
        if len(items) == 1:
            return items[0]
        return SearchOr(items=tuple(items))

    def parse_and(self) -> SearchExpression:
        items = [self.parse_unary()]
        while self._match_keyword("AND"):
            items.append(self.parse_unary())
        if len(items) == 1:
            return items[0]
        return SearchAnd(items=tuple(items))

    def parse_unary(self) -> SearchExpression:
        if self._match_keyword("NOT"):
            return SearchNot(item=self.parse_unary())
        return self.parse_primary()

    def parse_primary(self) -> SearchExpression:
        if self._match_kind("("):
            expr = self.parse_expression()
            self._expect_kind(")")
            return expr
        if self._peek_keyword("exists"):
            return self._parse_exists_like(SearchOperator.exists)
        if self._peek_keyword("missing"):
            return self._parse_exists_like(SearchOperator.missing)
        return self._parse_comparison()

    def _parse_exists_like(self, operator: SearchOperator) -> SearchExpression:
        self._expect_atom()
        self._expect_kind("(")
        field_ref = self._parse_field_ref()
        self._expect_kind(")")
        return SearchLeaf(fields=(field_ref,), operator=operator)

    def _parse_comparison(self) -> SearchExpression:
        field_ref = self._parse_field_ref()
        operator = self._parse_operator()
        value = self._parse_value()
        return SearchLeaf(
            fields=(field_ref,),
            operator=operator,
            values=(value,),
        )

    def _parse_field_ref(self) -> SearchFieldRef:
        token = self._peek()
        if token is None:
            raise ConfigError("Expected field reference in --where expression")
        if token.kind != "ATOM":
            raise ConfigError(f"Expected field reference, got: {token.value!r}")
        atom = token.value
        if atom.lower() == "config":
            self.pos += 1
            self._expect_kind("(")
            value = self._parse_value()
            self._expect_kind(")")
            return SearchFieldRef(name=value, is_config=True)
        self.pos += 1
        if atom not in _SUPPORTED_FIELDS:
            raise ConfigError(
                f"Unsupported search field: {atom!r}. Supported fields: {', '.join(sorted(_SUPPORTED_FIELDS))}"
            )
        return SearchFieldRef(name=atom)

    def _parse_operator(self) -> SearchOperator:
        token = self._peek()
        if token is None or token.kind != "OP":
            raise ConfigError("Expected operator in --where expression")
        self.pos += 1
        return SearchOperator(token.value)

    def _parse_value(self) -> str:
        token = self._peek()
        if token is None or token.kind not in {"STRING", "ATOM"}:
            raise ConfigError("Expected value in --where expression")
        self.pos += 1
        return token.value

    def _peek(self) -> Optional[_Token]:
        if self.pos >= len(self.tokens):
            return None
        return self.tokens[self.pos]

    def _match_kind(self, kind: str) -> bool:
        token = self._peek()
        if token is None or token.kind != kind:
            return False
        self.pos += 1
        return True

    def _expect_kind(self, kind: str) -> None:
        if not self._match_kind(kind):
            raise ConfigError(f"Expected {kind!r} in --where expression")

    def _expect_atom(self) -> None:
        token = self._peek()
        if token is None or token.kind != "ATOM":
            raise ConfigError("Expected identifier in --where expression")
        self.pos += 1

    def _peek_keyword(self, keyword: str) -> bool:
        token = self._peek()
        return bool(
            token and token.kind == "ATOM" and token.value.upper() == keyword.upper()
        )

    def _match_keyword(self, keyword: str) -> bool:
        if self._peek_keyword(keyword):
            self.pos += 1
            return True
        return False

    def expect_eof(self) -> None:
        token = self._peek()
        if token is not None:
            raise ConfigError(
                f"Unexpected token at end of --where expression: {token.value!r}"
            )


__all__ = ["build_search_query", "parse_where_clause"]
