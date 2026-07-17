from __future__ import annotations

from dataclasses import dataclass

from connectctl.services.failure_bundle.command_catalog import FailureCommandCatalog
from connectctl.services.failure_bundle.models import (
    FailureAnalysisContext,
    FailureRemediation,
)
from connectctl.services.failure_bundle.planner import FailureRemediationPlanner


def _context(*, error_message: str = "boom") -> FailureAnalysisContext:
    return FailureAnalysisContext.from_parts(
        command="apply",
        env="prod",
        stage="deploy",
        error=RuntimeError(error_message),
        manifest_meta={"name": "prod.demo.connector.0"},
        routing_payload={},
        pruned_config_keys=(),
        extra={"name": "prod.demo.connector.0"},
    )


@dataclass(frozen=True)
class StaticRule:
    category: str

    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None:
        return FailureRemediation(category=self.category, summary=self.category)


@dataclass(frozen=True)
class NoopRule:
    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None:
        return None


def test_planner_uses_first_matching_rule() -> None:
    planner = FailureRemediationPlanner(
        rules=(StaticRule("first"), StaticRule("second")),
        fallback_rule=StaticRule("fallback"),
    )

    remediation = planner.plan(_context(), FailureCommandCatalog())

    assert remediation.category == "first"


def test_planner_uses_fallback_when_no_rule_matches() -> None:
    planner = FailureRemediationPlanner(
        rules=(NoopRule(),),
        fallback_rule=StaticRule("fallback"),
    )

    remediation = planner.plan(_context(), FailureCommandCatalog())

    assert remediation.category == "fallback"
