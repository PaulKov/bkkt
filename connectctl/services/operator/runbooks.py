from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class RunbookSuggestion:
    id: str
    title: str
    path: str
    reason: str
    commands: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "path": self.path,
            "reason": self.reason,
            "commands": list(self.commands),
        }


@dataclass(frozen=True)
class RunbookRule:
    id: str
    title: str
    path: str
    patterns: tuple[str, ...]
    commands: tuple[str, ...] = ()

    def matches(self, text: str) -> bool:
        return any(
            re.search(pattern, text, flags=re.IGNORECASE) for pattern in self.patterns
        )


class RunbookRouter:
    """Small error-pattern router used by operator UX and failure hints."""

    def __init__(self, rules: Sequence[RunbookRule]):
        self.rules = tuple(rules)

    @classmethod
    def default(cls) -> "RunbookRouter":
        return cls(
            rules=(
                RunbookRule(
                    id="connect-control-plane",
                    title="Kafka Connect endpoint failover and offsets",
                    path="docs/CONNECT_CONTROL_PLANE.md",
                    patterns=(
                        "timeout",
                        "endpoint",
                        "404",
                        "offsets",
                        "connectors list",
                    ),
                    commands=(
                        "bkkt connect endpoints --env <env> --cluster <cluster>",
                    ),
                ),
                RunbookRule(
                    id="lifecycle",
                    title="Connector lifecycle disable/enable",
                    path="docs/LIFECYCLE.md",
                    patterns=("lifecycle", "disabled", "connectctl.lifecycle"),
                    commands=("bkkt apply --env <env> <manifest>",),
                ),
                RunbookRule(
                    id="search",
                    title="Search and explainable discovery",
                    path="docs/SEARCH.md",
                    patterns=("not found", "search", "topic", "table", "lineage"),
                    commands=(
                        "bkkt search --source both --env prod --cluster all --where '<query>'",
                    ),
                ),
                RunbookRule(
                    id="policies",
                    title="Config policies and guardrails",
                    path="docs/POLICIES.md",
                    patterns=("policy", "config_tests", "guardrail", "ADR"),
                    commands=("bkkt validate --env prod <manifest>",),
                ),
                RunbookRule(
                    id="schema-registry",
                    title="Schema Registry recovery is intentionally out of BKKT REST scope",
                    path="docs/CONNECT_CONTROL_PLANE.md",
                    patterns=(
                        "schema registry",
                        "schema-registry",
                        "Unknown magic byte",
                        "protobuf",
                    ),
                    commands=(
                        "bkkt connect offsets get --env <env> --cluster <cluster> --name <connector>",
                    ),
                ),
            )
        )

    def suggest(self, texts: Iterable[str]) -> tuple[RunbookSuggestion, ...]:
        haystack = "\n".join(str(text) for text in texts if str(text).strip())
        suggestions: list[RunbookSuggestion] = []
        for rule in self.rules:
            if rule.matches(haystack):
                suggestions.append(
                    RunbookSuggestion(
                        id=rule.id,
                        title=rule.title,
                        path=rule.path,
                        reason="Matched diagnostic text",
                        commands=rule.commands,
                    )
                )
        return tuple(dict((item.id, item) for item in suggestions).values())

    def suggest_for_discovery(self, result) -> tuple[RunbookSuggestion, ...]:
        texts: list[str] = [result.query_object, result.object_kind]
        for item in result.results:
            texts.append(item.facts.name)
            texts.extend(item.facts.consumed_topics)
            texts.extend(item.facts.produced_topics)
            texts.extend(item.facts.sink_table_full_names())
            texts.extend(item.facts.source_tables)
        if not result.results:
            texts.append("not found search")
        return self.suggest(texts)


__all__ = ["RunbookRouter", "RunbookRule", "RunbookSuggestion"]
