from __future__ import annotations

import re
from typing import List

from ..models import ConnectorManifest, Environment
from .policies_models import ENV_SENSITIVE_KEY_RE, PolicyIssue
from .policies_models import find_foreign_env_token
from .policies_utils import iter_strings_in_mapping

_TOPIC_PREFIX_KEYS = {
    "topic.prefix",
    "schema.history.internal.kafka.topic",
    "iceberg.control.topic",
    "transforms.replacetopicname.regex",
    "transforms.replacetopicname.replacement",
}
_EXPLICIT_TOPIC_PREFIXES = ("cdc.", "initial.")
_WAREHOUSE_KEYS = {
    "iceberg.catalog.glue.warehouse",
}


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _topic_item_has_expected_env_prefix(value: str, env: Environment) -> bool:
    vv = str(value).strip().lower()
    if not vv:
        return False

    for prefix in _EXPLICIT_TOPIC_PREFIXES:
        wanted = f"{prefix}{env.value}."
        if vv.startswith(wanted):
            return True

    return vv.startswith(f"{env.value}.")


def _should_skip_foreign_env_check(
    *,
    key: str,
    value: str,
    env: Environment,
) -> bool:
    vv = str(value).strip()
    if not vv:
        return False

    key_l = key.lower()
    if key_l == "topics":
        parts = _split_csv(vv)
        return bool(parts) and all(
            _topic_item_has_expected_env_prefix(item, env) for item in parts
        )

    if key_l in _TOPIC_PREFIX_KEYS:
        return _topic_item_has_expected_env_prefix(vv, env)

    if key_l in _WAREHOUSE_KEYS:
        lowered = vv.lower()
        if not lowered.startswith("s3://"):
            return False
        bucket = lowered.removeprefix("s3://").split("/", maxsplit=1)[0]
        return (
            re.search(
                rf"(?:^|[-_.]){re.escape(env.value)}(?:[-_.]|$)",
                bucket,
            )
            is not None
        )

    return False


def lint_runtime_manifest(
    manifest: ConnectorManifest,
    *,
    env: Environment,
) -> List[PolicyIssue]:
    """Runtime-проверки (по итоговому rendered manifest.config)."""
    issues: List[PolicyIssue] = []

    for k, v in iter_strings_in_mapping(manifest.config):
        k_norm = str(k).strip()
        vv = v.strip()
        if not vv:
            continue

        # env leakage: forbid obvious references to other environments in sensitive values.
        # We intentionally ignore config-provider placeholders (they can contain env names inside secret paths).
        if vv.startswith("${") and ":" in vv:
            continue
        if _should_skip_foreign_env_check(key=k_norm, value=vv, env=env):
            continue
        if (
            ENV_SENSITIVE_KEY_RE.search(k_norm)
            or vv.lower().startswith("s3://")
            or "cdc." in vv.lower()
        ):
            tok = find_foreign_env_token(vv, env)
            if tok:
                issues.append(
                    PolicyIssue(
                        severity="error",
                        policy="FOREIGN_ENV_REFERENCE",
                        manifest_path=str(manifest.info.relpath),
                        file_path=None,
                        key=k_norm,
                        message=f"Value appears to reference foreign env token '{tok}' while env is '{env.value}'.",
                        hint="Check topics / endpoints / buckets; prefer ${env} or ${env.short} in templates to avoid copy-paste leaks.",
                    )
                )

    # Mode inference warnings (Debezium-like sources only)
    if manifest.info.connector_type.value == "source" and manifest.info.mode is None:
        system_l = (manifest.info.system or "").lower()
        cls_l = (manifest.config.get("connector.class", "") or "").lower()
        is_debezium_like = ("debezium" in cls_l) or (
            system_l in {"postgres", "mysql", "mariadb"}
        )
        if is_debezium_like:
            connector_dir_l = (manifest.info.connector_dir or "").lower()
            remainder_l = (manifest.info.remainder or "").lower()
            name_l = (manifest.name or "").lower()

            # Signals in file/name (dot-style often includes ".cdc." / ".init." segments)
            cdc_signal = (
                (".cdc." in remainder_l)
                or (".cdc." in name_l)
                or ("__cdc__" in remainder_l)
                or ("__cdc__" in name_l)
                or ("_cdc_" in remainder_l)
                or ("_cdc_" in name_l)
            )
            init_signal = (
                (".init." in remainder_l)
                or (".init." in name_l)
                or ("__init__" in remainder_l)
                or ("__init__" in name_l)
                or ("_init_" in remainder_l)
                or ("_init_" in name_l)
                or ("initial" in remainder_l)
                or ("initial" in name_l)
            )

            # Weak signals in connector_dir
            if (
                ("cdc" in connector_dir_l)
                and not re.search(r"(^|[-_])cdc($|[-_])", connector_dir_l)
                and ("stream" not in connector_dir_l)
            ):
                cdc_signal = True
            if (
                ("init" in connector_dir_l)
                and not re.search(r"(^|[-_])init($|[-_])", connector_dir_l)
                and ("initial" not in connector_dir_l)
            ):
                init_signal = True

            if cdc_signal or init_signal:
                expected = (
                    "cdc"
                    if (cdc_signal and not init_signal)
                    else ("init" if (init_signal and not cdc_signal) else "cdc/init")
                )
                issues.append(
                    PolicyIssue(
                        severity="warn",
                        policy="MODE_NOT_RECOGNIZED",
                        manifest_path=str(manifest.info.relpath),
                        file_path=None,
                        key="connector_dir",
                        message=(
                            f"Connector looks like '{expected}' (based on name/filename/connector_dir hints), but mode couldn't be inferred "
                            f"(connector_dir='{manifest.info.connector_dir}'). Mode overlays will NOT be applied."
                        ),
                        hint=(
                            "For sources you can make mode explicit via dot-tokens in the connector name: '.cdc.' / '.init.' / '.initial.' "
                            "(token must be surrounded by dots), or rename connector_dir to include an unambiguous token: '__cdc__' or '__init__' "
                            "(preferred), or '_cdc_'/'-cdc-'/'_init_'/'-init-'. Alternatively set snapshot.mode explicitly in the connector all.json/base file "
                            "or override vars.debezium_snapshot_mode_cdc/debezium_snapshot_mode_init."
                        ),
                    )
                )

    return issues
