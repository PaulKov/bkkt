from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Sequence, Tuple

from ..connector_facts import ConnectorFacts
from .models import (
    SearchAnd,
    SearchExpression,
    SearchFieldRef,
    SearchLeaf,
    SearchMatchDetail,
    SearchMatchMode,
    SearchNot,
    SearchOperator,
    SearchOr,
)
from .provenance import related_occurrences, sources_for_match
from .variables import expand_value_template

_FUZZY_MATCH_THRESHOLD = 0.84


@dataclass(frozen=True)
class EvaluationResult:
    matched: bool
    details: Tuple[SearchMatchDetail, ...] = ()


class SearchEvaluator:
    def __init__(self, *, ignore_case: bool) -> None:
        self.ignore_case = ignore_case

    def evaluate(
        self, expression: SearchExpression, *, facts: ConnectorFacts
    ) -> EvaluationResult:
        if isinstance(expression, SearchLeaf):
            return self._evaluate_leaf(expression, facts=facts)
        if isinstance(expression, SearchAnd):
            return self._evaluate_and(expression, facts=facts)
        if isinstance(expression, SearchOr):
            return self._evaluate_or(expression, facts=facts)
        if isinstance(expression, SearchNot):
            inner = self.evaluate(expression.item, facts=facts)
            return EvaluationResult(matched=not inner.matched, details=())
        raise TypeError(f"Unsupported SearchExpression: {type(expression).__name__}")

    def _evaluate_and(
        self, expr: SearchAnd, *, facts: ConnectorFacts
    ) -> EvaluationResult:
        if not expr.items:
            return EvaluationResult(matched=True, details=())
        details: List[SearchMatchDetail] = []
        for item in expr.items:
            result = self.evaluate(item, facts=facts)
            if not result.matched:
                return EvaluationResult(matched=False, details=())
            details.extend(result.details)
        return EvaluationResult(matched=True, details=tuple(details))

    def _evaluate_or(
        self, expr: SearchOr, *, facts: ConnectorFacts
    ) -> EvaluationResult:
        matched_details: List[SearchMatchDetail] = []
        matched = False
        for item in expr.items:
            result = self.evaluate(item, facts=facts)
            if result.matched:
                matched = True
                matched_details.extend(result.details)
        return EvaluationResult(
            matched=matched,
            details=tuple(matched_details) if matched else (),
        )

    def _evaluate_leaf(
        self, expr: SearchLeaf, *, facts: ConnectorFacts
    ) -> EvaluationResult:
        if expr.operator in {SearchOperator.exists, SearchOperator.missing}:
            return self._evaluate_exists(expr, facts=facts)

        values_to_match = self._expand_expected_values(expr.values or (), facts=facts)
        if not values_to_match:
            return EvaluationResult(matched=False, details=())

        field_results: List[EvaluationResult] = []
        for field_ref in expr.fields:
            actual_values = self._resolve_values(facts, field_ref)
            field_results.append(
                self._evaluate_values(
                    facts=facts,
                    field_ref=field_ref,
                    operator=expr.operator,
                    actual_values=actual_values,
                    expected_values=values_to_match,
                    match_mode=expr.match_mode,
                )
            )

        matched_results = [item for item in field_results if item.matched]
        if matched_results:
            details: List[SearchMatchDetail] = []
            for item in matched_results:
                details.extend(item.details)
            return EvaluationResult(matched=True, details=tuple(details))
        return EvaluationResult(matched=False, details=())

    def _evaluate_exists(
        self, expr: SearchLeaf, *, facts: ConnectorFacts
    ) -> EvaluationResult:
        matched_details: List[SearchMatchDetail] = []
        exists = False
        for field_ref in expr.fields:
            actual_values = self._resolve_values(facts, field_ref)
            if actual_values:
                exists = True
                matched_details.append(
                    SearchMatchDetail(
                        field=field_ref.display(),
                        operator=SearchOperator.exists.value,
                        query_value=None,
                        matched_values=tuple(actual_values),
                        sources=sources_for_match(
                            facts=facts,
                            field_name=field_ref.name,
                            matched_values=actual_values,
                            config_key=field_ref.name if field_ref.is_config else None,
                        ),
                    )
                )

        if expr.operator == SearchOperator.exists:
            return EvaluationResult(
                matched=exists,
                details=tuple(matched_details) if exists else (),
            )
        return EvaluationResult(matched=not exists, details=())

    def _evaluate_values(
        self,
        *,
        facts: ConnectorFacts,
        field_ref: SearchFieldRef,
        operator: SearchOperator,
        actual_values: Sequence[str],
        expected_values: Sequence[str],
        match_mode: SearchMatchMode,
    ) -> EvaluationResult:
        if operator == SearchOperator.ne:
            return self._evaluate_not_equal(
                facts=facts,
                field_ref=field_ref,
                actual_values=actual_values,
                expected_values=expected_values,
                match_mode=match_mode,
            )

        matched_details: List[SearchMatchDetail] = []
        matched_expected = 0
        for expected in expected_values:
            matches = tuple(
                value
                for value in actual_values
                if self._value_matches(
                    value=value,
                    expected=expected,
                    operator=operator,
                    allow_value_regex=field_ref.name == "topics.pattern",
                )
            )
            if matches:
                matched_expected += 1
                matched_details.append(
                    SearchMatchDetail(
                        field=field_ref.display(),
                        operator=operator.value,
                        query_value=expected,
                        matched_values=matches,
                        sources=sources_for_match(
                            facts=facts,
                            field_name=field_ref.name,
                            matched_values=matches,
                            config_key=(
                                field_ref.name if field_ref.is_config else None
                            ),
                        ),
                        occurrences=related_occurrences(
                            facts=facts,
                            query_value=expected,
                            ignore_case=self.ignore_case,
                        ),
                    )
                )

        if match_mode == SearchMatchMode.all:
            return EvaluationResult(
                matched=matched_expected == len(expected_values),
                details=(
                    tuple(matched_details)
                    if matched_expected == len(expected_values)
                    else ()
                ),
            )
        return EvaluationResult(
            matched=matched_expected > 0,
            details=tuple(matched_details) if matched_expected > 0 else (),
        )

    def _evaluate_not_equal(
        self,
        *,
        facts: ConnectorFacts,
        field_ref: SearchFieldRef,
        actual_values: Sequence[str],
        expected_values: Sequence[str],
        match_mode: SearchMatchMode,
    ) -> EvaluationResult:
        results: List[bool] = []
        for expected in expected_values:
            results.append(
                not any(
                    self._value_matches(
                        value=value,
                        expected=expected,
                        operator=SearchOperator.eq,
                        allow_value_regex=field_ref.name == "topics.pattern",
                    )
                    for value in actual_values
                )
            )
        if match_mode == SearchMatchMode.all:
            matched = all(results)
        else:
            matched = any(results)
        details: tuple[SearchMatchDetail, ...] = ()
        if matched:
            details = (
                SearchMatchDetail(
                    field=field_ref.display(),
                    operator=SearchOperator.ne.value,
                    query_value=",".join(expected_values),
                    matched_values=tuple(actual_values),
                    sources=sources_for_match(
                        facts=facts,
                        field_name=field_ref.name,
                        matched_values=actual_values,
                        config_key=field_ref.name if field_ref.is_config else None,
                    ),
                ),
            )
        return EvaluationResult(matched=matched, details=details)

    def _resolve_values(
        self, facts: ConnectorFacts, field_ref: SearchFieldRef
    ) -> Tuple[str, ...]:
        if field_ref.is_config:
            return self._normalize_config_value(facts.config.get(field_ref.name))
        return tuple(facts.query_fields().get(field_ref.name, ()))

    @staticmethod
    def _normalize_config_value(raw: object) -> Tuple[str, ...]:
        if raw is None:
            return ()
        if isinstance(raw, (list, tuple, set)):
            return tuple(str(item).strip() for item in raw if str(item).strip())
        text = str(raw).strip()
        return (text,) if text else ()

    def _expand_expected_values(
        self, values: Sequence[str], *, facts: ConnectorFacts
    ) -> Tuple[str, ...]:
        expanded: list[str] = []
        for value in values:
            expanded.extend(expand_value_template(value, facts=facts))
        return tuple(dict.fromkeys(expanded))

    def _value_matches(
        self,
        *,
        value: str,
        expected: str,
        operator: SearchOperator,
        allow_value_regex: bool = False,
    ) -> bool:
        left = value
        right = expected
        if self.ignore_case and operator != SearchOperator.regex:
            left = left.lower()
            right = right.lower()

        if operator == SearchOperator.eq:
            return left == right or (
                allow_value_regex
                and self._regex_value_matches(pattern=value, expected=expected)
            )
        if operator == SearchOperator.prefix:
            return left.startswith(right)
        if operator == SearchOperator.suffix:
            return left.endswith(right)
        if operator == SearchOperator.regex:
            flags = re.IGNORECASE if self.ignore_case else 0
            return re.search(expected, value, flags=flags) is not None
        if operator == SearchOperator.fuzzy:
            return SequenceMatcher(None, left, right).ratio() >= _FUZZY_MATCH_THRESHOLD
        raise ValueError(f"Unsupported operator for value match: {operator}")

    def _regex_value_matches(self, *, pattern: str, expected: str) -> bool:
        flags = re.IGNORECASE if self.ignore_case else 0
        try:
            return re.search(pattern, expected, flags=flags) is not None
        except re.error:
            return False


__all__ = ["EvaluationResult", "SearchEvaluator"]
