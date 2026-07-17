from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ..models import ConnectorManifest
from ..settings_models import Settings
from ..var_providers import VarProviderContext, VarProviderRuntime
from .contracts import ProviderContractLoader, ProviderContractRunner
from .models import (
    ProviderContractResult,
    VarPreflightIssue,
    VarPreflightResult,
)
from .secrets import (
    SecretReferenceChecker,
    SecretReferenceScanner,
    StaticSecretIndex,
    UnverifiedSecretReferenceChecker,
)


@dataclass(frozen=True)
class DeployContextVarsPreflightService:
    """Run vars/provider/secret preflight against an already rendered manifest.

    This service intentionally does not render the manifest again. Apply and
    rollout pass the deploy-context provider variables captured by the renderer,
    so runtime vars, template instance vars, routing metadata and artifact
    pruning stay consistent with the config that would be sent to Kafka Connect.
    """

    settings: Settings

    def run(
        self,
        *,
        manifest: ConnectorManifest,
        provider_context: VarProviderContext | None,
        provider_contracts: Sequence[str | Path] | None = None,
        secret_index: str | Path | None = None,
        manifest_label: str | None = None,
    ) -> VarPreflightResult:
        suite = ProviderContractLoader(
            self.settings.repo.root,
            paths=provider_contracts,
        ).load()
        provider_results: tuple[ProviderContractResult, ...] = ()
        issues: tuple[VarPreflightIssue, ...] = ()
        if provider_context is not None:
            provider_results = ProviderContractRunner(
                VarProviderRuntime.from_settings(self.settings),
                suite,
            ).run(provider_context=provider_context)
            issues = tuple(
                issue
                for provider_result in provider_results
                for issue in provider_result.issues
            )
        elif suite.contracts:
            issues = (
                VarPreflightIssue(
                    code="provider_context_unavailable",
                    message=(
                        "Provider contracts were configured, but this manifest was "
                        "loaded from a rendered artifact without provider deploy context"
                    ),
                    severity="warning",
                    expected="render-context",
                    actual="artifact",
                    source=str(manifest.source_path),
                ),
            )

        refs = SecretReferenceScanner().scan_config(manifest.config)
        checker: SecretReferenceChecker
        if secret_index:
            checker = StaticSecretIndex.from_file(self.settings.repo.root, secret_index)
        else:
            checker = UnverifiedSecretReferenceChecker()
        secret_result = checker.check(refs)
        return VarPreflightResult(
            manifest=manifest_label or self._relative(manifest.source_path),
            provider_contracts=provider_results,
            secret_refs=secret_result.refs,
            issues=issues + secret_result.issues,
        )

    def _relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.settings.repo.root).as_posix()
        except ValueError:
            return str(path)
