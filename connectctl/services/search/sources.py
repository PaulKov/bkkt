from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Tuple

from ...app.context import CliContext
from ...cli_helpers.live_scopes import LiveScope, dedupe_live_scopes
from ...execution import ConcurrencyOptions, RateLimiter, map_collect
from ...models import Environment
from ...rendering.factory import build_renderer
from ...rendering.runtime_vars import load_runtime_vars
from ...repo import ConnectorRepo
from ...routing import ClusterRouter
from ..connector_facts import (
    ConnectorFacts,
    build_connector_facts_from_live_config,
    build_connector_facts_from_manifest,
)
from .models import (
    SearchAnd,
    SearchExpression,
    SearchFieldRef,
    SearchLeaf,
    SearchOperator,
    SearchOr,
    SearchQuery,
    SearchSource,
)

_FUZZY_MATCH_THRESHOLD = 0.84


def collect_repo_facts(
    *,
    ctx: CliContext,
    query: SearchQuery,
    args,
    logger,
) -> Tuple[List[ConnectorFacts], List[str]]:
    repo = ConnectorRepo(ctx.settings.repo, fs=ctx.fs)
    renderer = build_renderer(ctx.settings, fs=ctx.fs)
    runtime_vars = load_runtime_vars(args, ctx.repo_root)
    warnings: List[str] = []
    facts_list: List[ConnectorFacts] = []

    for env_value in query.envs:
        env = Environment.from_str(env_value)
        router = ClusterRouter(
            settings=ctx.settings,
            env=env,
            cli_cluster=None,
            suppress_tag_conflicts=False,
            logger=lambda msg: logger.warning("%s", msg),
        )
        for path in sorted(repo.iter_deployable_connector_files(env=env)):
            try:
                rr = renderer.render(path, runtime_vars=runtime_vars)
                decision, _debug = router.route_with_debug(
                    connector_name=rr.manifest.name,
                    connectctl_meta=rr.connectctl,
                    connectctl_sources=rr.connectctl_sources,
                )
                if (
                    query.cluster_filter
                    and decision.cluster_name != query.cluster_filter
                ):
                    continue
                relpath = _safe_relpath(path=path, repo_root=ctx.repo_root)
                facts_list.append(
                    build_connector_facts_from_manifest(
                        rr.manifest,
                        origin="repo",
                        path=relpath,
                        envs=(env.value,),
                        clusters=(decision.cluster_name,),
                    )
                )
            except Exception as exc:
                warnings.append(
                    f"repo:{_safe_relpath(path=path, repo_root=ctx.repo_root)}: {type(exc).__name__}: {exc}"
                )

    return facts_list, warnings


def collect_live_facts(
    *,
    ctx: CliContext,
    query: SearchQuery,
    args,
    logger,
) -> Tuple[List[ConnectorFacts], List[str]]:
    conc = ConcurrencyOptions.from_args(args)
    throttle = (
        RateLimiter(conc.rate_limit_per_second, burst=conc.burst)
        if conc.rate_limit_per_second > 0
        else None
    )
    warnings: List[str] = []
    facts_list: List[ConnectorFacts] = []

    scopes = _dedupe_live_scopes(ctx=ctx, query=query)
    for scope in scopes:
        try:
            target = ctx.connect_target(
                scope.primary_env,
                scope.primary_cluster,
                throttle=throttle,
            )
        except Exception as exc:
            warnings.append(
                f"live:{scope.primary_cluster}/{scope.primary_env.value}: {type(exc).__name__}: {exc}"
            )
            continue

        name_filter = _required_name_filter(
            query.expression, ignore_case=query.ignore_case
        )
        object_name_prefilter = _object_name_prefilter(
            query.expression, ignore_case=query.ignore_case
        )
        if query.live_candidate_names:
            names = list(dict.fromkeys(query.live_candidate_names))
        elif name_filter and name_filter.operator == SearchOperator.eq:
            names = list(name_filter.values)
        else:
            try:
                listed_names = list(target.client.list_connectors())
            except Exception as exc:
                warnings.append(
                    f"live:{scope.primary_cluster}/{scope.primary_env.value}: {type(exc).__name__}: {exc}"
                )
                continue
            names = (
                [name for name in listed_names if name_filter.matches(name)]
                if name_filter
                else listed_names
            )
            if object_name_prefilter and not name_filter:
                filtered_names = [
                    name for name in listed_names if object_name_prefilter.matches(name)
                ]
                if filtered_names or query.source == SearchSource.both:
                    names = filtered_names

        if not names:
            continue

        if not query.live_candidate_names:
            prime_config_endpoint = getattr(
                target.client, "prime_config_endpoint", None
            )
            if callable(prime_config_endpoint):
                prime_config_endpoint(names)

        def _fetch_config(name: str):
            fast_get = getattr(target.client, "get_config_optional_fast", None)
            if callable(fast_get):
                return fast_get(name)
            return target.client.get_config_optional(name)

        for result in map_collect(names, _fetch_config, jobs=conc.jobs):
            if result.error is not None:
                warnings.append(
                    f"live:{scope.primary_cluster}/{scope.primary_env.value}:{result.item}: {type(result.error).__name__}: {result.error}"
                )
                continue
            cfg = result.value
            if cfg is None:
                warnings.append(
                    f"live:{scope.primary_cluster}/{scope.primary_env.value}:{result.item}: config not found"
                )
                continue
            facts_list.append(
                build_connector_facts_from_live_config(
                    name=result.item,
                    cfg=cfg,
                    envs=tuple(alias.env for alias in scope.aliases),
                    clusters=tuple(alias.cluster for alias in scope.aliases),
                    alias_scopes=scope.aliases,
                )
            )

    return facts_list, warnings


@dataclass(frozen=True)
class _NameFilter:
    operator: SearchOperator
    values: Tuple[str, ...]
    ignore_case: bool = False

    def matches(self, name: str) -> bool:
        if not self.values:
            return True
        candidate = name.lower() if self.ignore_case else name
        values = (
            tuple(value.lower() for value in self.values)
            if self.ignore_case
            else self.values
        )
        if self.operator == SearchOperator.eq:
            return candidate in values
        if self.operator == SearchOperator.prefix:
            return any(candidate.startswith(value) for value in values)
        if self.operator == SearchOperator.suffix:
            return any(candidate.endswith(value) for value in values)
        if self.operator == SearchOperator.regex:
            return any(
                _safe_regex_search(value, name, ignore_case=self.ignore_case)
                for value in self.values
            )
        if self.operator == SearchOperator.fuzzy:
            return any(
                SequenceMatcher(None, candidate, value).ratio()
                >= _FUZZY_MATCH_THRESHOLD
                for value in values
            )
        return True


def _required_name_filter(
    expression: SearchExpression, *, ignore_case: bool
) -> _NameFilter | None:
    """Return a safe required name filter for live preselection.

    We only pre-filter when the query logically requires a connector-name match.
    OR expressions such as operator object discovery must stay full-scan capable,
    otherwise a table/topic lookup could miss live-only connectors.
    """

    if isinstance(expression, SearchLeaf):
        if _is_name_only_leaf(expression):
            return _NameFilter(
                operator=expression.operator,
                values=tuple(value for value in expression.values if value),
                ignore_case=ignore_case,
            )
        return None
    if isinstance(expression, SearchAnd):
        for item in expression.items:
            found = _required_name_filter(item, ignore_case=ignore_case)
            if found is not None:
                return found
    return None


def _is_name_only_leaf(leaf: SearchLeaf) -> bool:
    return (
        len(leaf.fields) == 1
        and isinstance(leaf.fields[0], SearchFieldRef)
        and leaf.fields[0].name == "name"
        and not leaf.fields[0].is_config
        and leaf.operator
        in {
            SearchOperator.eq,
            SearchOperator.prefix,
            SearchOperator.suffix,
            SearchOperator.regex,
            SearchOperator.fuzzy,
        }
    )


def _safe_regex_search(pattern: str, value: str, *, ignore_case: bool) -> bool:
    try:
        flags = re.IGNORECASE if ignore_case else 0
        return re.search(pattern, value, flags=flags) is not None
    except re.error:
        return False


@dataclass(frozen=True)
class _ObjectNamePrefilter:
    tokens: Tuple[str, ...]
    ignore_case: bool = False

    def matches(self, name: str) -> bool:
        candidate = name.lower() if self.ignore_case else name
        tokens = (
            tuple(token.lower() for token in self.tokens)
            if self.ignore_case
            else self.tokens
        )
        required = min(2, len(tokens))
        return sum(1 for token in tokens if token in candidate) >= required


def _object_name_prefilter(
    expression: SearchExpression, *, ignore_case: bool
) -> _ObjectNamePrefilter | None:
    values = _collect_object_values(expression)
    tokens = tuple(
        dict.fromkeys(token for value in values for token in _search_tokens(value))
    )
    if len(tokens) < 2:
        return None
    return _ObjectNamePrefilter(tokens=tokens, ignore_case=ignore_case)


def _collect_object_values(expression: SearchExpression) -> Tuple[str, ...]:
    if isinstance(expression, SearchLeaf):
        if expression.operator != SearchOperator.eq:
            return ()
        field_names = {field.name for field in expression.fields if not field.is_config}
        if not field_names.intersection(
            {
                "topics.any",
                "topics.pattern",
                "tables.source",
                "tables.sink",
                "tables.sink_full",
                "db.name",
                "sink.database",
            }
        ):
            return ()
        return tuple(value for value in expression.values if value)
    if isinstance(expression, SearchAnd):
        return tuple(
            value for item in expression.items for value in _collect_object_values(item)
        )
    if isinstance(expression, SearchOr):
        return tuple(
            value for item in expression.items for value in _collect_object_values(item)
        )
    return ()


def _search_tokens(value: str) -> Tuple[str, ...]:
    ignored = {
        "cdc",
        "clickhouse",
        "dbt",
        "dev",
        "events",
        "iceberg",
        "kafka",
        "mariadb",
        "mysql",
        "ods",
        "postgres",
        "prod",
        "raw",
        "sink",
        "source",
        "stage",
    }
    normalized = str(value or "").replace("__", ".").lower()
    tokens = []
    for token in re.split(r"[^a-z0-9_]+", normalized):
        if len(token) < 3 or token in ignored or token.isdigit():
            continue
        tokens.append(token)
    return tuple(tokens)


def _dedupe_live_scopes(*, ctx: CliContext, query: SearchQuery) -> List[LiveScope]:
    selected_cluster_groups = (
        [query.cluster_filter]
        if query.cluster_filter
        else sorted(ctx.settings.cluster_groups.keys())
    )
    return dedupe_live_scopes(
        settings=ctx.settings,
        envs=query.envs,
        cluster_groups=selected_cluster_groups,
    )


def _safe_relpath(*, path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except Exception:
        return str(path)


__all__ = ["collect_live_facts", "collect_repo_facts"]
