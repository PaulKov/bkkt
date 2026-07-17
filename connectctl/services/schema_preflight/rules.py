from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ...models import ConnectorManifest, ConnectorType
from .models import SchemaRisk


_PROTOBUF_CONVERTER_SUFFIX = "protobufconverter"


@dataclass(frozen=True)
class _NullableModeKey:
    key: str
    standard: bool


_NULLABLE_MODE_KEYS: tuple[_NullableModeKey, ...] = (
    _NullableModeKey("value.converter.schemas.enable", True),
    _NullableModeKey("value.converter.ignore.default.for.nullables", True),
    _NullableModeKey("value.converter.optional.for.nullables", True),
    _NullableModeKey("value.converter.wrapper.for.nullables", True),
    _NullableModeKey("value.converter.replace.null.with.default", False),
)

_CONVERTER_MODE_KEYS: tuple[str, ...] = (
    "decimal.handling.mode",
    "time.precision.mode",
    "converters",
    "datetime.type",
    "datetime.format.timestamp.zone",
)

_SMT_SHAPE_KEYS: tuple[str, ...] = (
    "transforms",
    "transforms.unwrap.type",
    "transforms.unwrap.add.fields",
    "transforms.unwrap.add.headers",
    "transforms.setTableName.type",
    "transforms.setTableName.route.field",
)


class SchemaRiskRules:
    def analyze(
        self,
        *,
        manifest: ConnectorManifest,
        existing_config: Mapping[str, Any] | None,
    ) -> tuple[SchemaRisk, ...]:
        if existing_config is None:
            return ()
        if manifest.info.connector_type is not ConnectorType.source:
            return ()
        risks: list[SchemaRisk] = []
        if _uses_protobuf_value_converter(manifest.config):
            risks.extend(
                [
                    *_nullable_semantics_risks(manifest.config, existing_config),
                    *_schema_change_subject_risks(manifest.config, existing_config),
                ]
            )
        risks.extend(
            [
                *_topic_namespace_risks(manifest.config, existing_config),
                *_converter_mode_risks(manifest.config, existing_config),
                *_smt_shape_risks(manifest.config, existing_config),
            ]
        )
        return tuple(risks)


def _nullable_semantics_risks(
    desired: Mapping[str, Any], existing: Mapping[str, Any]
) -> tuple[SchemaRisk, ...]:
    changed = []
    for item in _NULLABLE_MODE_KEYS:
        desired_value = _boolish(desired.get(item.key))
        if desired_value is None or desired_value != item.standard:
            continue
        existing_value = _boolish(existing.get(item.key))
        if existing_value == item.standard:
            continue
        changed.append(item.key)
    if not changed:
        return ()
    return (
        SchemaRisk(
            risk_id="protobuf_nullable_semantics_change",
            severity="block",
            message=(
                "Rendered config changes Protobuf nullable/default semantics for "
                "an existing source connector. This can create incompatible "
                "Schema Registry versions for legacy subjects."
            ),
            changed_keys=tuple(changed),
        ),
    )


def _schema_change_subject_risks(
    desired: Mapping[str, Any], existing: Mapping[str, Any]
) -> tuple[SchemaRisk, ...]:
    key = "include.schema.changes"
    if _boolish(desired.get(key)) is True and _boolish(existing.get(key)) is not True:
        return (
            SchemaRisk(
                risk_id="schema_change_subject_enabled",
                severity="block",
                message="Schema-change subject generation is being enabled in-place.",
                changed_keys=(key,),
            ),
        )
    return ()


def _topic_namespace_risks(
    desired: Mapping[str, Any], existing: Mapping[str, Any]
) -> tuple[SchemaRisk, ...]:
    changed = _changed_keys(desired, existing, ("topic.prefix",))
    if not changed:
        return ()
    return (
        SchemaRisk(
            risk_id="topic_prefix_or_subject_namespace_change",
            severity="block",
            message="Topic prefix/subject namespace changes can strand offsets or consumers.",
            changed_keys=changed,
        ),
    )


def _converter_mode_risks(
    desired: Mapping[str, Any], existing: Mapping[str, Any]
) -> tuple[SchemaRisk, ...]:
    changed = _changed_keys(desired, existing, _CONVERTER_MODE_KEYS)
    if not changed:
        return ()
    return (
        SchemaRisk(
            risk_id="converter_mode_change",
            severity="block",
            message="Decimal/temporal converter mode changes can alter downstream types.",
            changed_keys=changed,
        ),
    )


def _smt_shape_risks(
    desired: Mapping[str, Any], existing: Mapping[str, Any]
) -> tuple[SchemaRisk, ...]:
    changed = _changed_keys(desired, existing, _SMT_SHAPE_KEYS)
    if not changed:
        return ()
    return (
        SchemaRisk(
            risk_id="smt_envelope_or_metadata_shape_change",
            severity="block",
            message="SMT envelope/metadata shape changes can alter Kafka schema and routing.",
            changed_keys=changed,
        ),
    )


def _changed_keys(
    desired: Mapping[str, Any], existing: Mapping[str, Any], keys: tuple[str, ...]
) -> tuple[str, ...]:
    changed: list[str] = []
    for key in keys:
        if key not in desired:
            continue
        if _normalized(desired.get(key)) != _normalized(existing.get(key)):
            changed.append(key)
    return tuple(changed)


def _uses_protobuf_value_converter(config: Mapping[str, Any]) -> bool:
    converter = str(config.get("value.converter") or "").strip().lower()
    return converter.endswith(_PROTOBUF_CONVERTER_SUFFIX)


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
