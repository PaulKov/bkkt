from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ..rendering.factory import build_renderer
from ..settings_models import Settings
from ..var_providers import VarProviderContext, VarProviderRuntime
from .contracts import ProviderContractLoader, ProviderContractRunner
from .models import VarPreflightResult
from .secrets import (
    SecretReferenceChecker,
    SecretReferenceScanner,
    StaticSecretIndex,
    UnverifiedSecretReferenceChecker,
)


@dataclass(frozen=True)
class VarsPreflightService:
    settings: Settings

    def run(
        self,
        manifest_path: Path,
        *,
        provider_contracts: Sequence[str | Path] | None = None,
        secret_index: str | Path | None = None,
    ) -> VarPreflightResult:
        path = (
            manifest_path
            if manifest_path.is_absolute()
            else self.settings.repo.root / manifest_path
        )
        path = path.resolve()
        runtime = VarProviderRuntime.from_settings(self.settings)
        provider_context = self._provider_context(path)
        suite = ProviderContractLoader(
            self.settings.repo.root,
            paths=provider_contracts,
        ).load()
        provider_results = ProviderContractRunner(runtime, suite).run(
            provider_context=provider_context
        )
        rendered = build_renderer(self.settings).render(path)
        refs = SecretReferenceScanner().scan_config(rendered.manifest.config)
        checker: SecretReferenceChecker
        if secret_index:
            checker = StaticSecretIndex.from_file(self.settings.repo.root, secret_index)
        else:
            checker = UnverifiedSecretReferenceChecker()
        secret_result = checker.check(refs)
        issues = (
            tuple(
                issue
                for provider_result in provider_results
                for issue in provider_result.issues
            )
            + secret_result.issues
        )
        return VarPreflightResult(
            manifest=self._relative(path),
            provider_contracts=provider_results,
            secret_refs=secret_result.refs,
            issues=issues,
        )

    def _provider_context(self, manifest_path: Path) -> VarProviderContext:
        from dataclasses import replace

        from ..settings_models import ComputedVarsSettings, VarProvidersSettings

        base_settings = replace(
            self.settings,
            var_providers=VarProvidersSettings(enabled=False),
            computed_vars=ComputedVarsSettings(enabled=False),
        )
        rendered = build_renderer(base_settings).render(manifest_path)
        return VarProviderContext.from_flat_context(
            rendered.placeholder_context,
            sources=rendered.placeholder_sources,
            repo_root=self.settings.repo.root,
            manifest_path=manifest_path,
        )

    def _relative(self, path: Path) -> str:
        try:
            return path.relative_to(self.settings.repo.root).as_posix()
        except ValueError:
            return str(path)
