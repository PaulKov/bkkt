from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ...exceptions import ValidationError
from ...models import ConnectorManifest
from ..schema_preflight.models import PreflightDecision
from ..schema_preflight.service import SchemaPreflightService


_PROTOBUF_CONVERTER_SUFFIX = "protobufconverter"


@dataclass(frozen=True)
class NullableModeKey:
    key: str
    standard: bool


_NULLABLE_MODE_KEYS: tuple[NullableModeKey, ...] = (
    NullableModeKey("value.converter.schemas.enable", True),
    NullableModeKey("value.converter.ignore.default.for.nullables", True),
    NullableModeKey("value.converter.optional.for.nullables", True),
    NullableModeKey("value.converter.wrapper.for.nullables", True),
    NullableModeKey("value.converter.replace.null.with.default", False),
)


def run_schema_registry_preflight(
    *,
    manifest: ConnectorManifest,
    existing_config: Mapping[str, Any] | None,
    connectctl_meta: Mapping[str, Any] | None,
    repo_allowlist: Sequence[Mapping[str, Any]] | None = None,
) -> None:
    """Block unsafe in-place Protobuf nullable-shape migrations.

    Debezium-generated Protobuf schemas are not available as static files at
    render time, so ``bkkt apply`` cannot POST an exact candidate schema to
    Schema Registry before the connector produces an event. The next best
    deploy-time contract is to detect the config changes that deterministically
    change the generated Protobuf shape for already-existing subjects and force
    an explicit migration plan.

    New connectors/topics are allowed to use the platform standard. Existing
    connectors are blocked only when a rendered config attempts to move from a
    legacy nullable/default mode into the platform nullable-preserving mode.
    """

    meta = dict(connectctl_meta or {})
    meta["name"] = manifest.name
    result = SchemaPreflightService(repo_allowlist=repo_allowlist).analyze(
        manifest=manifest,
        existing_config=existing_config,
        connectctl_meta=meta,
    )
    if result.decision is not PreflightDecision.block:
        return

    nullable_risk = next(
        (
            risk
            for risk in result.risks
            if risk.risk_id == "protobuf_nullable_semantics_change" and not risk.allowed
        ),
        None,
    )
    if nullable_risk is None:
        blocked = ", ".join(risk.risk_id for risk in result.risks if not risk.allowed)
        raise ValidationError(
            "Schema Registry preflight blocked an unsafe in-place schema-affecting "
            f"change for {manifest.name}. Risk ids: {blocked}."
        )

    changes = _risky_nullable_shape_changes(
        desired=manifest.config,
        existing=existing_config or {},
    )
    exception = _migration_exception(connectctl_meta or {})
    if exception.is_complete:
        return

    changed_keys = ", ".join(
        f"{change.key}: {change.existing!r} -> {change.desired!r}" for change in changes
    )
    missing = ", ".join(exception.missing_fields) or "-"
    raise ValidationError(
        "Schema Registry preflight blocked an in-place Protobuf nullable schema "
        f"migration for {manifest.name}. The rendered config changes nullable "
        "converter semantics for an existing connector, which can create a new "
        "Schema Registry subject version incompatible with the latest legacy "
        "subject. Use a new topic/V2 contour, keep the legacy nullable mode, or "
        "add a documented connectctl.schema_registry_preflight migration "
        "exception after running an explicit SR compatibility and consumer "
        "impact check. "
        f"Changed keys: {changed_keys}. Missing exception fields: {missing}."
    )


@dataclass(frozen=True)
class _NullableShapeChange:
    key: str
    existing: str | None
    desired: str | None


@dataclass(frozen=True)
class _MigrationException:
    is_complete: bool
    missing_fields: tuple[str, ...]


def _uses_protobuf_value_converter(config: Mapping[str, Any]) -> bool:
    converter = str(config.get("value.converter") or "").strip().lower()
    return converter.endswith(_PROTOBUF_CONVERTER_SUFFIX)


def _risky_nullable_shape_changes(
    *, desired: Mapping[str, Any], existing: Mapping[str, Any]
) -> tuple[_NullableShapeChange, ...]:
    changes: list[_NullableShapeChange] = []
    for item in _NULLABLE_MODE_KEYS:
        desired_value = _boolish(desired.get(item.key))
        if desired_value is None:
            continue
        if desired_value != item.standard:
            continue
        existing_value = _boolish(existing.get(item.key))
        if existing_value == item.standard:
            continue
        changes.append(
            _NullableShapeChange(
                key=item.key,
                existing=_normalized(existing.get(item.key)),
                desired=_normalized(desired.get(item.key)),
            )
        )
    return tuple(changes)


def _migration_exception(meta: Mapping[str, Any]) -> _MigrationException:
    raw = meta.get("schema_registry_preflight")
    if not isinstance(raw, Mapping):
        return _MigrationException(
            is_complete=False,
            missing_fields=(
                "schema_registry_preflight.allow_in_place_nullable_migration",
                "schema_registry_preflight.ticket",
                "schema_registry_preflight.reason",
                "schema_registry_preflight.migration_plan",
                "schema_registry_preflight.subjects",
            ),
        )

    required: dict[str, Any] = {
        "allow_in_place_nullable_migration": raw.get(
            "allow_in_place_nullable_migration"
        ),
        "ticket": raw.get("ticket"),
        "reason": raw.get("reason"),
        "migration_plan": raw.get("migration_plan"),
        "subjects": raw.get("subjects"),
    }
    missing: list[str] = []
    for key, value in required.items():
        if key == "allow_in_place_nullable_migration":
            if _boolish(value) is not True:
                missing.append(f"schema_registry_preflight.{key}")
            continue
        if key == "subjects":
            if not _non_empty_sequence(value):
                missing.append(f"schema_registry_preflight.{key}")
            continue
        if not str(value or "").strip():
            missing.append(f"schema_registry_preflight.{key}")

    return _MigrationException(
        is_complete=not missing,
        missing_fields=tuple(missing),
    )


def _non_empty_sequence(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Sequence):
        return any(str(item or "").strip() for item in value)
    return False


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    return None


def _normalized(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip()
