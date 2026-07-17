from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from ..exceptions import ValidationError
from ..logging_utils import get_logger
from ..models import ConnectorManifest, Environment
from ..config_models import NamingConfig
from .config_tests_runner import ConfigTestRunner


def validate_manifest(
    manifest: ConnectorManifest,
    *,
    strict_naming: bool = False,
    policies: bool = False,
    policy_env: Optional[Environment] = None,
    policy_layers: Optional[Sequence[Path]] = None,
    config_test_runner: Optional[ConfigTestRunner] = None,
    config_test_context: Optional[Mapping[str, Any]] = None,
    naming: Optional[NamingConfig] = None,
    logger=None,
) -> None:
    """Базовая валидация отрендеренного manifest.

    Проверяет:
    - наличие имени и конфига
    - что все значения конфига — строки (Kafka Connect требует strings)
    - что плейсхолдеры ${...} не остались в name/config (кроме ConfigProvider синтаксиса)
    - опционально: config-tests
    - опционально: строгий нейминг
    - опционально: политики безопасности
    """

    log = get_logger(logger)

    if not manifest.name:
        raise ValidationError(f"Empty connector name in {manifest.source_path}")
    if not isinstance(manifest.config, dict) or not manifest.config:
        raise ValidationError(
            f"Empty config for {manifest.name} in {manifest.source_path}"
        )
    if "connector.class" not in manifest.config:
        # Not strictly required for all connectors, but for most it's essential
        raise ValidationError(
            f"Missing 'connector.class' in config for {manifest.name} ({manifest.source_path})"
        )

    # Kafka Connect REST expects config map values to be strings.
    non_str = [
        (k, type(v).__name__)
        for k, v in manifest.config.items()
        if not isinstance(v, str)
    ]
    if non_str:
        preview = ", ".join([f"{k}={t}" for k, t in non_str[:10]])
        more = f" (+{len(non_str) - 10} more)" if len(non_str) > 10 else ""
        raise ValidationError(
            f"Non-string config values in {manifest.name} ({manifest.source_path}): {preview}{more}. "
            "Kafka Connect expects all config values to be strings."
        )

    # If config redundantly contains 'name', it must match the connector name.
    if "name" in manifest.config and manifest.config["name"] != manifest.name:
        raise ValidationError(
            f"Config contains name='{manifest.config['name']}' but manifest name is '{manifest.name}' "
            f"({manifest.source_path})"
        )

    # Disallow unresolved placeholders in the connector name itself.
    if "${" in manifest.name:
        raise ValidationError(
            f"Unresolved placeholder in connector name '{manifest.name}' ({manifest.source_path}). "
            "Name must be a concrete string after rendering."
        )

    placeholder_re = re.compile(r"\$\{([^}]+)\}")
    for key, value in manifest.config.items():
        if "${" not in value:
            continue
        for m in placeholder_re.finditer(value):
            inner = (m.group(1) or "").strip()
            if not inner:
                raise ValidationError(
                    f"Unresolved placeholder '${{}}' in config key '{key}' for {manifest.name} ({manifest.source_path})"
                )

            # Allow Kafka Connect ConfigProvider placeholders like ${secretManager:...}.
            # Disallow our internal function placeholders (${fn:...}) if they survived rendering.
            if ":" in inner:
                prefix = inner.split(":", 1)[0].strip()
                if prefix == "fn":
                    raise ValidationError(
                        f"Unresolved function placeholder '${{{inner}}}' in config key '{key}' for {manifest.name} ({manifest.source_path}). "
                        "Function placeholders must be fully resolved during render."
                    )
                continue

            raise ValidationError(
                f"Unresolved placeholder '${{{inner}}}' in config key '{key}' for {manifest.name} ({manifest.source_path}). "
                "If this is a Kafka Connect ConfigProvider value, use the provider syntax like ${secretManager:...}."
            )

    # Config test-suite validation (optional, configured via repo config_tests/).
    if config_test_runner is not None:
        issues = config_test_runner.validate(
            manifest, context=dict(config_test_context or {})
        )
        if issues:
            warnings = [i for i in issues if i.severity == "warning"]
            errors = [i for i in issues if i.severity == "error"]

            for w in warnings:
                key_part = f" (key: {w.key})" if w.key else ""
                log.warning(
                    "WARNING [config-test:%s] %s: %s%s",
                    w.rule_id,
                    manifest.name,
                    w.message,
                    key_part,
                )

            if errors:
                joined = "\n".join(
                    f"- [{e.rule_id}] {e.message}{(f' (key: {e.key})' if e.key else '')}"
                    for e in errors
                )
                raise ValidationError(
                    f"Config tests failed for {manifest.name} ({manifest.source_path}):\n{joined}"
                )

    if strict_naming:
        from .naming_strict import validate_strict_naming

        validate_strict_naming(manifest, naming=naming)

    if policies:
        from .policies_validate import validate_policies

        validate_policies(manifest, env=policy_env, layers=policy_layers)
