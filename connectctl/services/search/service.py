from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import List, Optional

from ...app.context import CliContext
from ...cli_helpers.default_scope_ux import (
    confirm_broad_scope,
    effective_value,
    log_effective_values,
)
from ...cli_helpers.explicit_args import was_explicit
from ...exceptions import ConfigError
from ...logging_utils import get_logger
from ...output import resolve_output_format
from ...output import write_payload, write_text
from .evaluator import SearchEvaluator
from .formatting import emit_search_output
from .models import SearchResultItem, SearchRunResult, SearchSource
from .query import build_search_query
from .sources import collect_live_facts, collect_repo_facts
from .variables import list_search_variables, render_search_variables_text


@dataclass
class SearchService:
    ctx: CliContext
    logger: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        self.log = get_logger(self.logger or self.ctx.logger)

    def run(self, args) -> int:
        if bool(getattr(args, "list_vars", False)):
            if str(getattr(args, "output", "text") or "text") == "text":
                write_text(render_search_variables_text())
            else:
                write_payload(
                    {
                        "variables": [
                            item.to_dict() for item in list_search_variables()
                        ],
                        "dynamic_variables": [
                            {
                                "name": 'config("key.with.dots")',
                                "description": "config value by exact key",
                            }
                        ],
                    },
                    fmt=resolve_output_format(args),
                )
            return 0

        config_path = getattr(self.ctx, "config_path", None)
        if config_path is not None and not config_path.exists():
            raise ConfigError(
                "Config file not found. Create connectctl.yaml or use --list-vars for config-less search help."
            )

        query = build_search_query(args)
        if (
            query.cluster_filter
            and query.cluster_filter not in self.ctx.settings.cluster_groups
        ):
            raise ConfigError(
                f"Unknown cluster group for --cluster: {query.cluster_filter!r}. "
                f"Expected one of: {', '.join(sorted(self.ctx.settings.cluster_groups)) or '<none>'}"
            )
        log_effective_values(
            self.log,
            command="search",
            values=(
                effective_value(args, "source", query.source.value),
                effective_value(
                    args,
                    "env",
                    (
                        "all"
                        if tuple(query.envs) == ("dev", "stage", "prod")
                        else ",".join(query.envs)
                    ),
                ),
                effective_value(args, "cluster", query.cluster_filter or "all"),
                effective_value(args, "view", query.view.value),
                effective_value(args, "jobs", getattr(args, "jobs", None)),
            ),
        )
        if _requires_broad_live_confirmation(args, query=query):
            if not confirm_broad_scope(
                args,
                prompt=(
                    "Продолжить широкий live search с default scope "
                    f"(env={','.join(query.envs)}, cluster={query.cluster_filter or 'all'})?"
                ),
                logger=self.log,
            ):
                return 1
        evaluator = SearchEvaluator(ignore_case=query.ignore_case)
        warnings: List[str] = []
        results: List[SearchResultItem] = []

        if query.source in {SearchSource.repo, SearchSource.both}:
            repo_facts, repo_warnings = collect_repo_facts(
                ctx=self.ctx,
                query=query,
                args=args,
                logger=self.log,
            )
            warnings.extend(repo_warnings)
            results.extend(
                self._evaluate(
                    repo_facts, evaluator=evaluator, expression=query.expression
                )
            )

        if query.source in {SearchSource.live, SearchSource.both}:
            live_facts, live_warnings = collect_live_facts(
                ctx=self.ctx,
                query=query,
                args=args,
                logger=self.log,
            )
            warnings.extend(live_warnings)
            results.extend(
                self._evaluate(
                    live_facts, evaluator=evaluator, expression=query.expression
                )
            )

        results.sort(
            key=lambda item: (
                item.facts.origin,
                ",".join(item.facts.envs),
                ",".join(item.facts.clusters),
                item.facts.name,
                item.facts.path or "",
            )
        )
        if query.limit:
            results = results[: query.limit]

        payload = SearchRunResult(
            query=query,
            results=results,
            warnings=list(dict.fromkeys(warnings)),
        )
        emit_search_output(
            payload,
            fmt=resolve_output_format(args),
            view=query.view,
        )
        return 0

    @staticmethod
    def _evaluate(
        facts_list, *, evaluator: SearchEvaluator, expression
    ) -> List[SearchResultItem]:
        items: List[SearchResultItem] = []
        for facts in facts_list:
            result = evaluator.evaluate(expression, facts=facts)
            if result.matched:
                items.append(SearchResultItem(facts=facts, matched=result.details))
        return items


def _requires_broad_live_confirmation(args, *, query) -> bool:
    if query.source not in {SearchSource.live, SearchSource.both}:
        return False
    env_is_all = tuple(query.envs) == ("dev", "stage", "prod")
    cluster_is_all = query.cluster_filter is None
    return (env_is_all and not was_explicit(args, "env")) or (
        cluster_is_all and not was_explicit(args, "cluster")
    )


__all__ = ["SearchService"]
