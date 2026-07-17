from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ...exceptions import ConfigError
from ...cli_helpers.timeout_args import timeout_seconds_from_args
from ...models import Environment


@dataclass(frozen=True)
class ApplyOptions:
    """Parsed options for apply-side effects.

    This is intentionally kept as a plain dataclass so it can be:
      - created from CLI args
      - injected into services/classes
      - trivially tested
    """

    env: Environment
    dry_run: bool

    rollback_on_fail: bool
    connect_validate: bool

    skip_if_unchanged: bool
    force: bool

    drop_if_exists: bool
    drop_if_failed: bool

    wait_seconds: Optional[float]
    timeout_seconds: float
    poll_interval_seconds: float

    smoke: bool
    smoke_strict: bool

    auto_catalog: bool
    schema_preflight: bool
    schema_preflight_reason: str | None
    vars_preflight: bool
    vars_preflight_reason: str | None
    vars_preflight_provider_contracts: tuple[str, ...]
    vars_preflight_secret_index: str | None

    @classmethod
    def from_args(cls, args: Any, *, env: Environment) -> "ApplyOptions":
        dry_run = bool(getattr(args, "dry_run", False))

        health_gates = bool(getattr(args, "health_gates", False))

        rollback_on_fail = getattr(args, "rollback_on_fail", None)
        if rollback_on_fail is None:
            rollback_on_fail = env in {Environment.stage, Environment.prod}
        if health_gates:
            rollback_on_fail = True

        connect_validate = bool(getattr(args, "connect_validate", True)) or health_gates

        skip_if_unchanged = bool(getattr(args, "skip_if_unchanged", True))
        force = bool(getattr(args, "force", False))

        drop_if_exists = bool(getattr(args, "drop_if_exists", False))
        drop_if_failed = bool(getattr(args, "drop_if_failed", False))

        wait_seconds = getattr(args, "wait_seconds", None)
        wait_seconds_f: Optional[float] = None
        if wait_seconds is not None:
            wait_seconds_f = float(wait_seconds)

        timeout_seconds = timeout_seconds_from_args(args, default=300.0)
        poll_interval_seconds = float(getattr(args, "poll_interval_seconds", 5))

        smoke = bool(getattr(args, "smoke", True)) or health_gates
        smoke_strict = bool(getattr(args, "smoke_strict", False))

        auto_catalog = bool(getattr(args, "auto_catalog", True))
        schema_preflight = bool(getattr(args, "schema_preflight", True))
        schema_preflight_reason = getattr(args, "schema_preflight_reason", None)
        if not schema_preflight and not str(schema_preflight_reason or "").strip():
            raise ConfigError(
                "--no-schema-preflight requires --schema-preflight-reason for auditability"
            )

        vars_preflight = bool(getattr(args, "vars_preflight", True))
        vars_preflight_reason = getattr(args, "vars_preflight_reason", None)
        if not vars_preflight and not str(vars_preflight_reason or "").strip():
            raise ConfigError(
                "--no-vars-preflight requires --vars-preflight-reason for auditability"
            )
        provider_contracts = tuple(
            str(item)
            for item in (getattr(args, "vars_preflight_provider_contract", None) or ())
            if str(item).strip()
        )
        secret_index_raw = getattr(args, "vars_preflight_secret_index", None)
        secret_index = (
            str(secret_index_raw).strip() if secret_index_raw is not None else None
        )

        return cls(
            env=env,
            dry_run=dry_run,
            rollback_on_fail=bool(rollback_on_fail),
            connect_validate=connect_validate,
            skip_if_unchanged=skip_if_unchanged,
            force=force,
            drop_if_exists=drop_if_exists,
            drop_if_failed=drop_if_failed,
            wait_seconds=wait_seconds_f,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            smoke=smoke,
            smoke_strict=smoke_strict,
            auto_catalog=auto_catalog,
            schema_preflight=schema_preflight,
            schema_preflight_reason=(
                str(schema_preflight_reason).strip()
                if schema_preflight_reason is not None
                else None
            ),
            vars_preflight=vars_preflight,
            vars_preflight_reason=(
                str(vars_preflight_reason).strip()
                if vars_preflight_reason is not None
                else None
            ),
            vars_preflight_provider_contracts=provider_contracts,
            vars_preflight_secret_index=secret_index,
        )
