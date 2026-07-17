from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple

from .diffing import (
    ConfigKeyChanges,
    config_key_changes,
    config_unified_diff,
    normalize_config,
)
from .utils.masking import is_sensitive_key


@dataclass(frozen=True)
class ConfigComparison:
    """Normalized comparison between desired and actual connector configs."""

    connector_name: str
    desired: Dict[str, str]
    actual: Dict[str, str]
    desired_masked: Dict[str, str]
    actual_masked: Dict[str, str]
    changes: ConfigKeyChanges
    unified_diff: str

    @property
    def in_sync(self) -> bool:
        return self.changes.is_empty()

    @property
    def changed_keys(self) -> Tuple[str, ...]:
        return tuple(
            sorted(
                [
                    *self.changes.added.keys(),
                    *self.changes.removed.keys(),
                    *self.changes.changed.keys(),
                ]
            )
        )

    def diff_payload(self) -> Dict[str, Any]:
        changed = {}
        for key, (actual_value, desired_value) in self.changes.changed.items():
            changed[key] = {
                "actual": _mask_value(key, actual_value),
                "desired": _mask_value(key, desired_value),
            }

        return {
            "in_sync": self.in_sync,
            "counts": {
                "only_in_desired": len(self.changes.added),
                "only_in_actual": len(self.changes.removed),
                "changed": len(self.changes.changed),
            },
            "only_in_desired": {
                key: _mask_value(key, value)
                for key, value in self.changes.added.items()
            },
            "only_in_actual": {
                key: _mask_value(key, value)
                for key, value in self.changes.removed.items()
            },
            "changed": changed,
            "changed_keys": list(self.changed_keys),
        }


def compare_connector_configs(
    *,
    connector_name: str,
    desired: Mapping[str, Any],
    actual: Mapping[str, Any],
) -> ConfigComparison:
    desired_norm = normalize_config(desired, mask_secrets=False)
    actual_norm = normalize_config(actual, mask_secrets=False)
    changes = config_key_changes(desired=desired_norm, existing=actual_norm)
    return ConfigComparison(
        connector_name=connector_name,
        desired=desired_norm,
        actual=actual_norm,
        desired_masked=normalize_config(desired, mask_secrets=True),
        actual_masked=normalize_config(actual, mask_secrets=True),
        changes=changes,
        unified_diff=config_unified_diff(
            connector_name=connector_name,
            desired=desired_norm,
            existing=actual_norm,
            fromfile="desired",
            tofile="actual",
        ),
    )


def _mask_value(key: str, value: str) -> str:
    if is_sensitive_key(key):
        return "***"
    return value
