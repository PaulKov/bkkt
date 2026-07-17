from __future__ import annotations

import json
from typing import Any, Dict
from urllib.parse import quote

from ..exceptions import ConnectApiError, ValidationError
from ..models import ConnectorManifest
from .client_base import ConnectClientBase


class ConnectValidationMixin(ConnectClientBase):
    """Миксин с методами валидации конфигов через Kafka Connect."""

    def validate_config(
        self, connector_class: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate a connector config using Kafka Connect plugin validation.

        Kafka Connect REST API endpoint (Apache / Confluent):
          PUT /connector-plugins/<connector_class>/config/validate

        Notes:
        - This does NOT create or update a connector.
        - The returned JSON contains `error_count` and per-field errors.
        - Some deployments (custom proxies / filters) may only allow POST; we fallback on 405.
        """

        if not connector_class:
            raise ValueError("connector_class must not be empty")

        # connector.class is part of the URL path segment; quote to be safe.
        # Keep common safe characters to keep logs readable.
        plugin = quote(str(connector_class), safe="._-")

        method = "PUT"
        resp = self._request(
            method,
            f"/connector-plugins/{plugin}/config/validate",
            headers={"Content-Type": "application/json"},
            data=json.dumps(config),
        )

        if resp.status_code == 405:
            method = "POST"
            resp = self._request(
                method,
                f"/connector-plugins/{plugin}/config/validate",
                headers={"Content-Type": "application/json"},
                data=json.dumps(config),
            )

        if resp.status_code != 200:
            raise ConnectApiError(
                f"{method} /connector-plugins/{connector_class}/config/validate failed: "
                f"HTTP {resp.status_code}: {resp.text}"
            )
        return resp.json()

    @staticmethod
    def _format_plugin_validation_errors(
        result: Dict[str, Any], *, max_errors: int = 20
    ) -> str:
        """Extract and format per-field validation errors from Connect response."""

        errs = []
        configs = result.get("configs", []) or []
        if isinstance(configs, list):
            for c in configs:
                if not isinstance(c, dict):
                    continue

                # Kafka Connect versions differ: errors can be in `errors` or in `value.errors`.
                ce = c.get("errors")
                if not isinstance(ce, list) or not ce:
                    v = c.get("value")
                    if isinstance(v, dict):
                        ce = v.get("errors")
                if not isinstance(ce, list) or not ce:
                    continue

                # Field name is typically `definition.name` (or `value.name` in some versions).
                field = None
                d = c.get("definition")
                if isinstance(d, dict):
                    field = d.get("name")
                if not field:
                    v = c.get("value")
                    if isinstance(v, dict):
                        field = v.get("name")
                field = field or c.get("name") or "<unknown>"

                for e in ce:
                    errs.append(f"- {field}: {e}")

        if not errs:
            # Some Connect versions return error_count without detailed per-field errors.
            errs = ["- (Kafka Connect did not provide per-field errors)"]

        if len(errs) > max_errors:
            more = len(errs) - max_errors
            errs = errs[:max_errors] + [f"- ... (+{more} more)"]

        return "\n".join(errs)

    @staticmethod
    def _detect_common_validation_hints(
        config: Dict[str, Any], *, max_items: int = 10
    ) -> str:
        """Heuristics to make opaque Connect validation failures more actionable.

        We avoid printing sensitive values. The output is best-effort and should not be treated as a
        strict validator.
        """

        suspicious: list[str] = []

        def _is_sensitive_key(k: str) -> bool:
            k_l = k.lower()
            return any(
                tok in k_l
                for tok in (
                    "password",
                    "secret",
                    "token",
                    "private",
                    "sasl.jaas",
                    "jaas.config",
                    "api.key",
                    "apikey",
                )
            )

        def _looks_like_unresolved_bkkt_placeholder(v: str) -> bool:
            vv = v.strip()
            if not (vv.startswith("${") and vv.endswith("}")):
                return False
            inner = vv[2:-1]
            # ConfigProvider placeholders contain ':' (e.g. secretManager:file:env:...).
            # Our default placeholder is the ONLY colon from ':-'.
            if ":-" in inner and inner.count(":") == 1:
                return True
            # Plain ${var}
            return ":" not in inner

        def _looks_like_config_provider_placeholder(v: str) -> bool:
            """Kafka Connect ConfigProvider placeholder, e.g. ${secretManager:...}.

            Important: do NOT treat BKKT default placeholders `${var:-default}` as ConfigProviders.
            """

            vv = v.strip()
            if not (vv.startswith("${") and vv.endswith("}")):
                return False
            inner = vv[2:-1]
            # Our default placeholder uses `:-` and contains exactly one colon.
            if ":-" in inner and inner.count(":") == 1:
                return False
            return ":" in inner

        for k, v in (config or {}).items():
            if not isinstance(k, str):
                continue
            if not isinstance(v, str):
                continue

            vv = v.strip()
            if not vv:
                continue

            # Common init-template placeholders
            if "CHANGE_ME" in vv:
                suspicious.append(
                    f"- {k}: обнаружен плейсхолдер CHANGE_ME (вероятно, не переопределено после init)"
                )
                continue

            # Unresolved BKKT placeholders (not Kafka Connect ConfigProviders)
            if _looks_like_unresolved_bkkt_placeholder(vv):
                suspicious.append(
                    f"- {k}: похоже, остался неразрешённый плейсхолдер '{'***' if _is_sensitive_key(k) else vv}' (проверь overrides/vars)"
                )
                continue

            # Ports should be numeric (common failure cause)
            if (
                k.lower().endswith(".port")
                and (not vv.isdigit())
                and (not _looks_like_config_provider_placeholder(vv))
            ):
                suspicious.append(
                    f"- {k}: значение порта выглядит некорректно (ожидается число){'' if _is_sensitive_key(k) else f': {vv!r}'}"
                )

            if len(suspicious) >= max_items:
                break

        if not suspicious:
            return ""

        tail = ""
        if len(suspicious) >= max_items:
            tail = "\n- ..."
        return (
            "\n\nПодсказки (best-effort):\n"
            + "\n".join(suspicious[:max_items])
            + tail
            + "\n\nЕсли ошибка остаётся непрозрачной: запусти `bkkt validate-connect --max-errors 50 ...` (или включи `--no-connect-validate` временно, НЕ рекомендуется)."
        )

    @staticmethod
    def _looks_like_config_provider_placeholder(v: str) -> bool:
        """Detect Kafka Connect ConfigProvider placeholders: `${provider:...}`.

        We intentionally treat `${var:-default}` and `${var}` (BKKT placeholders) as *not* ConfigProviders.
        """

        vv = str(v).strip()
        if not (vv.startswith("${") and vv.endswith("}")):
            return False
        inner = vv[2:-1]
        # Our default placeholder uses `:-` and contains exactly one colon.
        if ":-" in inner and inner.count(":") == 1:
            return False
        return ":" in inner

    @classmethod
    def _sanitize_config_for_plugin_validation(
        cls, config: Dict[str, Any]
    ) -> tuple[Dict[str, Any], list[str]]:
        """Replace ConfigProvider placeholders with safe dummy values.

        Some Kafka Connect deployments do not resolve ConfigProviders for the *validate* endpoint
        (or resolve them only on create/update). In that case, plugin validators may reject
        placeholder strings like `${secretManager:...}`.

        We do a best-effort substitution to validate everything *except* the secret-backed values.
        Returns (sanitized_config, replaced_fields).
        """

        if not config:
            return {}, []

        replaced: list[str] = []
        out: Dict[str, Any] = dict(config)

        def _dummy_value_for_key(k: str) -> str:
            kl = k.lower()

            # Numbers
            if kl.endswith(".port"):
                return "5432"
            if kl in {"tasks.max"}:
                return "1"

            # Hostnames
            if kl.endswith(".hostname") or kl.endswith(".host") or "hostname" in kl:
                return "bkkt-host"

            # URLs
            if kl.endswith(".url") or "schema.registry" in kl:
                return "http://bkkt.local"

            # Kafka bootstrap
            if "bootstrap.servers" in kl:
                return "bkkt-broker:9092"

            # Topics
            if kl.endswith(".topic") or "topic.prefix" in kl or kl.endswith("topic"):
                return "bkkt.topic"

            # DB names/users
            if kl.endswith(".dbname") or kl in {"database.dbname"}:
                return "bkkt_db"
            if kl.endswith(".user") or kl.endswith(".username"):
                return "bkkt_user"

            # Fallback string
            return "bkkt_placeholder"

        for k, v in config.items():
            if not isinstance(k, str):
                continue
            if not isinstance(v, str):
                continue
            if cls._looks_like_config_provider_placeholder(v):
                out[k] = _dummy_value_for_key(k)
                replaced.append(k)

        return out, replaced

    def validate_manifest(
        self, manifest: ConnectorManifest, *, max_errors: int = 20
    ) -> Dict[str, Any]:
        """Validate a rendered manifest against the target Connect cluster.

        Raises :class:`~connectctl.exceptions.ValidationError` if Connect reports validation errors.
        """

        connector_class = str(manifest.config.get("connector.class") or "").strip()
        if not connector_class:
            raise ValidationError(
                f"Missing 'connector.class' in config for {manifest.name} ({manifest.source_path})"
            )

        raw_config = manifest.config
        result = self.validate_config(connector_class, raw_config)
        try:
            error_count = int(result.get("error_count") or 0)
        except Exception:
            error_count = 0

        if error_count > 0:
            # If the config contains ConfigProvider placeholders, some Connect clusters return
            # false-positive errors on the validate endpoint (placeholders are not resolved).
            # We try a best-effort second pass with dummy values to surface "real" problems.
            sanitized_cfg, replaced_fields = (
                self._sanitize_config_for_plugin_validation(raw_config)
            )

            if replaced_fields:
                try:
                    sanitized_result = self.validate_config(
                        connector_class, sanitized_cfg
                    )
                    sanitized_error_count = int(
                        sanitized_result.get("error_count") or 0
                    )
                except Exception:
                    sanitized_result = None
                    sanitized_error_count = -1

                if sanitized_result is not None and sanitized_error_count == 0:
                    # Proceed, but warn that validate endpoint likely does not resolve ConfigProviders.
                    # This is not necessarily a deployment blocker (create/update may still resolve).
                    try:
                        self._log.warning(
                            "Kafka Connect validate returned errors for %s, but succeeded after "
                            "ConfigProvider placeholder substitution (replaced %s field(s)). "
                            "Your Connect cluster may not resolve ConfigProviders on the validate endpoint.",
                            manifest.name,
                            len(replaced_fields),
                        )
                    except Exception:
                        # logger is optional
                        pass

                    sanitized_result.setdefault("_bkkt", {})
                    sanitized_result["_bkkt"].update(
                        {
                            "validation_mode": "placeholder-substitution",
                            "replaced_fields": replaced_fields,
                        }
                    )
                    return sanitized_result

                # If still failing, show both raw and sanitized errors.
                raw_details = self._format_plugin_validation_errors(
                    result, max_errors=max_errors
                )
                raw_details += self._detect_common_validation_hints(raw_config)

                if sanitized_result is not None and sanitized_error_count >= 0:
                    sanitized_details = self._format_plugin_validation_errors(
                        sanitized_result, max_errors=max_errors
                    )
                    note = (
                        "\n\nNOTE: Конфиг содержит значения вида `${provider:...}` (ConfigProvider). "
                        "Некоторые кластера Kafka Connect НЕ подставляют такие значения для validate endpoint, "
                        "из-за чего появляются ложные ошибки формата.\n"
                        "BKKT сделал второй прогон валидации, заменив такие значения на безопасные заглушки, "
                        "чтобы выявить реальные проблемы (список заменённых полей см. выше).\n"
                    )
                    repl = "\n".join(f"- {k}" for k in replaced_fields[:50])
                    if len(replaced_fields) > 50:
                        repl += f"\n- ... (+{len(replaced_fields) - 50} more)"

                    raise ValidationError(
                        "Kafka Connect plugin validation failed for "
                        f"{manifest.name} (connector.class={connector_class}, error_count={error_count}):\n"
                        f"Raw errors:\n{raw_details}\n"
                        f"\nAfter placeholder substitution (ConfigProviders mocked):\n{sanitized_details}"
                        f"\n\nReplaced fields:\n{repl}"
                        f"{note}"
                    )

            # Default: no placeholder substitution, show raw errors.
            details = self._format_plugin_validation_errors(
                result, max_errors=max_errors
            )
            details += self._detect_common_validation_hints(raw_config)
            raise ValidationError(
                "Kafka Connect plugin validation failed for "
                f"{manifest.name} (connector.class={connector_class}, error_count={error_count}):\n{details}"
            )

        return result
