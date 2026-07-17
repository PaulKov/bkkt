from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Protocol

import yaml

from ..exceptions import ConnectCtlError
from .models import SecretReference, SecretReferenceCheckResult, VarPreflightIssue


class SecretReferenceChecker(Protocol):
    def check(
        self, refs: tuple[SecretReference, ...]
    ) -> SecretReferenceCheckResult: ...


class SecretReferenceScanner:
    _SECRET_RE = re.compile(r"\$\{secretManager:([^}:]+):([^}]+)\}")

    def scan_config(self, config: Mapping[str, Any]) -> tuple[SecretReference, ...]:
        refs: list[SecretReference] = []
        for key, value in sorted(config.items()):
            if not isinstance(value, str):
                continue
            for match in self._SECRET_RE.finditer(value):
                refs.append(
                    SecretReference(
                        provider="secretManager",
                        secret=match.group(1),
                        field=match.group(2),
                        config_key=key,
                    )
                )
        return tuple(refs)


class StaticSecretIndex:
    """Deterministic secret checker used by preflight and tests.

    The index intentionally stores only secret names and available fields. It does
    not store or print secret values.
    """

    def __init__(self, index: Mapping[str, Mapping[str, set[str]]]) -> None:
        self._index = {
            provider: {secret: set(fields) for secret, fields in secrets.items()}
            for provider, secrets in index.items()
        }

    @classmethod
    def from_file(cls, repo_root: Path, raw_path: str | Path) -> "StaticSecretIndex":
        path = Path(raw_path)
        if not path.is_absolute():
            path = repo_root / path
        path = path.resolve()
        try:
            path.relative_to(repo_root.resolve())
        except ValueError as e:
            raise ConnectCtlError("secret index path must stay inside repo root") from e
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ConnectCtlError(f"{path}: secret index must be a mapping")
        index: dict[str, dict[str, set[str]]] = {}
        for provider, secrets_raw in raw.items():
            if not isinstance(secrets_raw, dict):
                raise ConnectCtlError(f"{path}: {provider} must be a mapping")
            provider_index: dict[str, set[str]] = {}
            for secret, payload in secrets_raw.items():
                if isinstance(payload, dict):
                    fields = payload.get("keys", ()) or ()
                else:
                    fields = payload or ()
                if not isinstance(fields, list):
                    raise ConnectCtlError(
                        f"{path}: {provider}.{secret}.keys must be a list"
                    )
                provider_index[str(secret)] = {str(item) for item in fields}
            index[str(provider)] = provider_index
        return cls(index)

    def check(self, refs: tuple[SecretReference, ...]) -> SecretReferenceCheckResult:
        issues: list[VarPreflightIssue] = []
        payload_refs: list[dict[str, Any]] = []
        seen_missing_secret: set[tuple[str, str]] = set()
        for ref in refs:
            provider_secrets = self._index.get(ref.provider, {})
            if ref.secret not in provider_secrets:
                payload_refs.append(ref.to_payload(status="failed"))
                marker = (ref.provider, ref.secret)
                if marker not in seen_missing_secret:
                    seen_missing_secret.add(marker)
                    issues.append(
                        VarPreflightIssue(
                            code="secret_not_found",
                            message=(
                                f"Secret {ref.secret!r} for provider {ref.provider!r} "
                                "is not present in the preflight index"
                            ),
                            key=ref.secret,
                            expected="present",
                            actual=None,
                            source=ref.config_key,
                        )
                    )
                continue
            if ref.field not in provider_secrets[ref.secret]:
                payload_refs.append(ref.to_payload(status="failed"))
                issues.append(
                    VarPreflightIssue(
                        code="secret_key_missing",
                        message=(
                            f"Secret {ref.secret!r} is missing field {ref.field!r}"
                        ),
                        key=f"{ref.secret}.{ref.field}",
                        expected="present",
                        actual=None,
                        source=ref.config_key,
                    )
                )
                continue
            payload_refs.append(ref.to_payload(status="ok"))
        return SecretReferenceCheckResult(
            refs=tuple(payload_refs),
            issues=tuple(issues),
        )


class UnverifiedSecretReferenceChecker:
    def check(self, refs: tuple[SecretReference, ...]) -> SecretReferenceCheckResult:
        return SecretReferenceCheckResult(
            refs=tuple(ref.to_payload(status="unverified") for ref in refs),
            issues=tuple(
                VarPreflightIssue(
                    code="secret_ref_unverified",
                    message=(
                        f"Secret reference {ref.secret!r}:{ref.field!r} was found, "
                        "but no exact secret checker was configured"
                    ),
                    severity="warning",
                    key=f"{ref.secret}.{ref.field}",
                    source=ref.config_key,
                )
                for ref in refs
            ),
        )
