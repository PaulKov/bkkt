from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ..exceptions import RenderError, ValidationError

BKKT_META_KEY = "bkkt"
UNSET_CONFIG_KEYS_KEY = "unset_config_keys"
LEGACY_DOTTED_UNSET_CONFIG_KEYS_KEY = "bkkt.unset_config_keys"


def extract_bkkt_meta(obj: Mapping[str, Any]) -> dict[str, Any]:
    """Extract BKKT-only metadata from a manifest fragment.

    BKKT metadata is intentionally not Kafka Connect config.  The canonical JSON
    shape is ``{"bkkt": {"unset_config_keys": [...]}}``.  The dotted top-level
    key is accepted for compatibility with early design notes and ad-hoc files.
    """

    meta: dict[str, Any] = {}

    raw_bkkt = obj.get(BKKT_META_KEY)
    if raw_bkkt is not None:
        if not isinstance(raw_bkkt, Mapping):
            raise RenderError("'bkkt' must be an object/dict")
        meta.update(dict(raw_bkkt))

    if LEGACY_DOTTED_UNSET_CONFIG_KEYS_KEY in obj:
        existing = normalize_unset_config_keys(
            meta.get(UNSET_CONFIG_KEYS_KEY),
            source="bkkt.unset_config_keys",
        )
        extra = normalize_unset_config_keys(
            obj.get(LEGACY_DOTTED_UNSET_CONFIG_KEYS_KEY),
            source=LEGACY_DOTTED_UNSET_CONFIG_KEYS_KEY,
        )
        meta[UNSET_CONFIG_KEYS_KEY] = [*existing, *extra]

    return meta


def normalize_unset_config_keys(raw: Any, *, source: str) -> tuple[str, ...]:
    """Return normalized config keys declared as explicit unsets."""

    if raw is None:
        return ()
    if isinstance(raw, str):
        candidates: Iterable[Any] = [raw]
    elif isinstance(raw, Iterable) and not isinstance(raw, (bytes, bytearray, Mapping)):
        candidates = raw
    else:
        raise RenderError(f"{source} must be a string or list of strings")

    out: list[str] = []
    for item in candidates:
        key = str(item).strip()
        if key:
            out.append(key)
    return tuple(dict.fromkeys(out))


def apply_unset_config_keys(
    config: Mapping[str, Any],
    unset_keys: Iterable[str],
) -> dict[str, Any]:
    """Remove exact Kafka Connect config keys from a rendered config map."""

    out = dict(config)
    for key in unset_keys:
        out.pop(str(key), None)
    return out


def find_forbidden_final_config_values(config: Mapping[str, Any]) -> dict[str, str]:
    """Find final config values that must never be sent to Kafka Connect.

    Legacy manifests may still use JSON null as a layer-local delete sentinel, but
    by the time we validate/apply/render an effective connector config there must
    be no ``None`` and no literal string ``"null"`` left.
    """

    bad: dict[str, str] = {}
    for key, value in config.items():
        key_s = str(key)
        if value is None:
            bad[key_s] = "json-null"
            continue
        if isinstance(value, str) and value.strip().lower() == "null":
            bad[key_s] = "string-null"
    return bad


def assert_final_config_has_no_nulls(
    config: Mapping[str, Any],
    *,
    connector_name: str,
    command: str,
) -> None:
    bad = find_forbidden_final_config_values(config)
    if not bad:
        return

    keys = ", ".join(f"{key} ({kind})" for key, kind in sorted(bad.items()))
    raise ValidationError(
        f"{command}: rendered config for {connector_name} contains forbidden null "
        f"values: {keys}. Use bkkt.unset_config_keys for inherited-key removal; "
        "final Kafka Connect payloads must not contain JSON null or string 'null'."
    )
