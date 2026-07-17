from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

from ..exceptions import ConnectCtlError
from ..var_providers import VarProviderContext, VarProviderRuntime
from ..var_providers.models import VarProviderRunResult
from ..vars_contracts import (
    VarsRedactor,
    VarsSchema,
    VarsSchemaEntry,
    VarsSchemaValidator,
)
from .models import (
    ProviderContract,
    ProviderContractResult,
    ProviderContractSuite,
    VarPreflightIssue,
)


class ProviderContractLoader:
    DEFAULT_GLOB = "bkkt/var_providers/contracts/**/*.yaml"

    def __init__(
        self,
        repo_root: Path,
        *,
        paths: Sequence[str | Path] | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.paths = tuple(paths or ())

    def load(self) -> ProviderContractSuite:
        contracts: dict[str, ProviderContract] = {}
        for path in self._iter_paths():
            for contract in self._load_file(path).contracts:
                if contract.provider in contracts:
                    raise ConnectCtlError(
                        "provider_contract_duplicate: "
                        f"Provider contract {contract.provider!r} is declared more than once."
                    )
                contracts[contract.provider] = contract
        return ProviderContractSuite(
            contracts=tuple(contracts[name] for name in sorted(contracts))
        )

    def _iter_paths(self) -> Iterable[Path]:
        if not self.paths:
            yield from sorted(self.repo_root.glob(self.DEFAULT_GLOB))
            return
        for raw in self.paths:
            path = Path(raw)
            if not path.is_absolute():
                path = self.repo_root / path
            path = path.resolve()
            try:
                path.relative_to(self.repo_root)
            except ValueError as e:
                raise ConnectCtlError(
                    "provider contract path must stay inside repo root"
                ) from e
            if path.is_dir():
                yield from sorted(path.rglob("*.yaml"))
            elif path.exists():
                yield path

    def _load_file(self, path: Path) -> ProviderContractSuite:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ConnectCtlError(f"{path}: provider contract file must be a mapping")
        providers = raw.get("providers", {}) or {}
        if not isinstance(providers, dict):
            raise ConnectCtlError(f"{path}: `providers` must be a mapping")

        contracts: list[ProviderContract] = []
        for provider, payload in providers.items():
            if not isinstance(provider, str) or not provider.strip():
                raise ConnectCtlError(
                    f"{path}: provider names must be non-empty strings"
                )
            if not isinstance(payload, dict):
                raise ConnectCtlError(f"{path}: providers.{provider} must be a mapping")
            contracts.append(_contract_from_mapping(provider.strip(), payload, path))
        return ProviderContractSuite(tuple(contracts))


def _contract_from_mapping(
    provider: str,
    payload: dict[str, Any],
    path: Path,
) -> ProviderContract:
    provides_raw = payload.get("provides", {}) or {}
    if not isinstance(provides_raw, dict):
        raise ConnectCtlError(
            f"{path}: providers.{provider}.provides must be a mapping"
        )
    capabilities = payload.get("capabilities")
    if capabilities is None:
        capabilities = []
    if not isinstance(capabilities, list):
        raise ConnectCtlError(
            f"{path}: providers.{provider}.capabilities must be a list"
        )
    provides = tuple(
        _entry_from_mapping(str(key).strip(), value or {})
        for key, value in provides_raw.items()
    )
    return ProviderContract(
        provider=provider,
        capabilities=tuple(
            str(item).strip() for item in capabilities if str(item).strip()
        ),
        provides=provides,
        source_path=path,
    )


def _entry_from_mapping(key: str, payload: dict[str, Any]) -> VarsSchemaEntry:
    if not key:
        raise ConnectCtlError("provider contract keys must be non-empty strings")
    if not isinstance(payload, dict):
        raise ConnectCtlError(f"provider contract entry {key!r} must be a mapping")
    raw_type = str(payload.get("type", "any")).strip().lower()
    if raw_type == "integer":
        raw_type = "int"
    if raw_type not in {"string", "int", "float", "bool", "number", "any"}:
        raise ConnectCtlError(
            f"Unsupported provider contract type for {key!r}: {raw_type!r}"
        )
    enum = payload.get("enum", ()) or ()
    if enum and not isinstance(enum, list):
        raise ConnectCtlError(f"provider contract {key!r}.enum must be a list")
    return VarsSchemaEntry(
        key=key,
        type=raw_type,  # type: ignore[arg-type]
        required=bool(payload.get("required", True)),
        enum=tuple(enum),
        pattern=str(payload["pattern"]) if payload.get("pattern") is not None else None,
        sensitive=bool(payload.get("sensitive", False)),
        description=str(payload.get("description", "") or ""),
    )


@dataclass(frozen=True)
class ProviderContractRunner:
    runtime: VarProviderRuntime
    suite: ProviderContractSuite

    def run(
        self,
        *,
        provider_context: VarProviderContext,
        provider_name: str | None = None,
    ) -> tuple[ProviderContractResult, ...]:
        contracts = (
            (self.suite.get(provider_name),) if provider_name else self.suite.contracts
        )
        results: list[ProviderContractResult] = []
        for contract in contracts:
            if contract is None:
                continue
            results.append(self._run_one(contract, provider_context))
        return tuple(results)

    def _run_one(
        self,
        contract: ProviderContract,
        provider_context: VarProviderContext,
    ) -> ProviderContractResult:
        issues: list[VarPreflightIssue] = []
        descriptor = self.runtime.registry.get(contract.provider)
        expected_capabilities = set(contract.capabilities)
        actual_capabilities = set(descriptor.capabilities)
        if expected_capabilities and expected_capabilities != actual_capabilities:
            issues.append(
                VarPreflightIssue(
                    code="provider_capability_mismatch",
                    provider=contract.provider,
                    message=(
                        f"Variable provider {contract.provider!r} capabilities do not "
                        "match its contract"
                    ),
                    expected=sorted(expected_capabilities),
                    actual=sorted(actual_capabilities),
                    source=str(contract.source_path) if contract.source_path else None,
                )
            )

        result = self.runtime.evaluate_one(
            contract.provider,
            provider_context.variables.values,
            provider_context=provider_context,
        )
        values = _values_from_run(result)
        issues.extend(_missing_output_issues(contract, values))
        issues.extend(_schema_issues(contract, values))
        redactor = VarsRedactor(_schema_from_contract(contract))
        redacted_values = redactor.redact_mapping(values)
        redacted_issues = [_redact_issue(issue, redactor) for issue in issues]
        return ProviderContractResult(
            provider=contract.provider,
            status="failed" if redacted_issues else "ok",
            values=redacted_values,
            issues=tuple(redacted_issues),
        )


class ProviderContractInferer:
    def infer(self, run_result: VarProviderRunResult) -> ProviderContractSuite:
        provides = tuple(
            VarsSchemaEntry(
                key=item.key,
                type=_infer_type(item.value),  # type: ignore[arg-type]
                required=True,
                description=(
                    "Inferred by `bkkt vars providers contract infer`; "
                    "review sensitive/pattern/capabilities before committing."
                ),
            )
            for item in run_result.values
        )
        return ProviderContractSuite(
            contracts=(
                ProviderContract(
                    provider=run_result.provider.name,
                    provides=provides,
                    capabilities=run_result.provider.capabilities,
                ),
            )
        )


def _values_from_run(run_result: VarProviderRunResult) -> dict[str, Any]:
    return {item.key: item.value for item in run_result.values}


def _missing_output_issues(
    contract: ProviderContract,
    values: dict[str, Any],
) -> list[VarPreflightIssue]:
    issues: list[VarPreflightIssue] = []
    for entry in contract.provides:
        if entry.required and entry.key not in values:
            issues.append(
                VarPreflightIssue(
                    code="provider_contract_missing_output",
                    provider=contract.provider,
                    key=entry.key,
                    message=(
                        f"Variable provider {contract.provider!r} must return "
                        f"{entry.key!r}"
                    ),
                    expected="present",
                    actual=None,
                    source=str(contract.source_path) if contract.source_path else None,
                )
            )
    return issues


def _schema_issues(
    contract: ProviderContract,
    values: dict[str, Any],
) -> list[VarPreflightIssue]:
    schema = _schema_from_contract(contract)
    result = VarsSchemaValidator().validate(
        schema,
        values,
        sources={key: f"provider:{contract.provider}" for key in values},
    )
    issues: list[VarPreflightIssue] = []
    for issue in result.issues:
        if issue.code == "required_missing":
            continue
        issues.append(
            VarPreflightIssue(
                code=issue.code,
                provider=contract.provider,
                key=issue.key,
                message=issue.message,
                severity=issue.severity,
                expected=issue.expected,
                actual=issue.actual,
                source=issue.source,
            )
        )
    return issues


def _schema_from_contract(contract: ProviderContract) -> VarsSchema:
    return VarsSchema(path=contract.source_path, entries=contract.provides)


def _redact_issue(
    issue: VarPreflightIssue, redactor: VarsRedactor
) -> VarPreflightIssue:
    if not issue.key or not redactor.is_sensitive(issue.key):
        return issue
    return VarPreflightIssue(
        code=issue.code,
        message=issue.message,
        severity=issue.severity,
        provider=issue.provider,
        key=issue.key,
        expected=issue.expected,
        actual="<redacted>" if issue.actual is not None else None,
        source=issue.source,
    )


def _infer_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    return "any"
