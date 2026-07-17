from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .command_catalog import FailureCommandCatalog
from .models import FailureAnalysisContext, FailureRemediation
from .rules import (
    ConnectEndpointHealthRule,
    ConnectValidationRule,
    ConnectorExistsRule,
    ConnectorMissingRule,
    DeployFailureRule,
    EnvMismatchRule,
    GenericRule,
    LiveConfigOperationRule,
    LivePayloadInputRule,
    LocalValidationRule,
    StatusOutputModeRule,
    TagConflictRule,
    TlsTruststoreRule,
)


class FailureRemediationRule(Protocol):
    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None: ...


def default_rules() -> tuple[FailureRemediationRule, ...]:
    return (
        TlsTruststoreRule(),
        TagConflictRule(),
        EnvMismatchRule(),
        StatusOutputModeRule(),
        LivePayloadInputRule(),
        ConnectorExistsRule(),
        ConnectorMissingRule(),
        LiveConfigOperationRule(),
        LocalValidationRule(),
        ConnectValidationRule(),
        ConnectEndpointHealthRule(),
        DeployFailureRule(),
    )


@dataclass(frozen=True)
class FailureRemediationPlanner:
    rules: tuple[FailureRemediationRule, ...] = field(default_factory=default_rules)
    fallback_rule: FailureRemediationRule = field(default_factory=GenericRule)

    def plan(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation:
        for rule in self.rules:
            remediation = rule.apply(context, commands)
            if remediation is not None:
                return remediation

        fallback = self.fallback_rule.apply(context, commands)
        if fallback is None:
            raise RuntimeError("Fallback remediation rule returned no remediation")
        return fallback
