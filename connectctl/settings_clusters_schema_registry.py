from __future__ import annotations

from typing import Any, Mapping, Optional

from .models import SchemaRegistryConfig


def parse_schema_registry_config(obj: Any) -> Optional[SchemaRegistryConfig]:
    """Parse optional Schema Registry settings from a cluster env block.

    Supported shapes:

    ```yaml
    schema_registry:
      urls: ["http://sr-a:8081", "http://sr-b:8081"]
      auth:
        type: basic
        username: user
        password: pass
      timeout_seconds: 10
    ```

    For small repos, a flat `url` or `urls` string is also accepted. Multiple
    URLs can be comma-separated.
    """

    if not isinstance(obj, Mapping):
        return None

    raw_urls = obj.get("urls") or obj.get("url") or obj.get("schema_registry_url")
    urls = _split_urls(raw_urls)
    if not urls:
        return None

    username = obj.get("username")
    password = obj.get("password")
    auth = obj.get("auth")
    if isinstance(auth, Mapping):
        auth_type = str(auth.get("type", "")).strip().lower()
        if auth_type in {"basic", "userpass", "username_password"}:
            username = auth.get("username") or username
            password = auth.get("password") or password

    timeout = obj.get("timeout_seconds", obj.get("timeout", 10.0))
    try:
        timeout_seconds = float(timeout)
    except (TypeError, ValueError):
        timeout_seconds = 10.0

    return SchemaRegistryConfig(
        urls=tuple(urls),
        username=str(username) if username is not None else None,
        password=str(password) if password is not None else None,
        timeout_seconds=timeout_seconds,
    )


def _split_urls(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [part.strip().rstrip("/") for part in raw.split(",") if part.strip()]
    if isinstance(raw, (list, tuple)):
        return [str(part).strip().rstrip("/") for part in raw if str(part).strip()]
    return []
