from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from ..models import Environment


@dataclass(frozen=True)
class PolicyIssue:
    """Замечание политики (lint)."""

    severity: str  # "error" | "warn"
    policy: str
    manifest_path: str
    file_path: Optional[str]
    key: Optional[str]
    message: str
    hint: Optional[str] = None


# ---------------------------------------------------------------------------
# Политики / константы
# ---------------------------------------------------------------------------

# Config keys that must NOT contain a hard-coded bootstrap server list.
BOOTSTRAP_KEYS = {
    "bootstrap.servers",
    "schema.history.internal.kafka.bootstrap.servers",
    "iceberg.kafka.bootstrap.servers",
}

# Any config key ending with schema.registry.url should not be hard-coded.
SCHEMA_REGISTRY_SUFFIX = "schema.registry.url"

ENV_SENSITIVE_KEY_RE = re.compile(
    r"(bootstrap|schema\.registry|topics?|topic\.prefix|warehouse|bucket|catalog|control)",
    re.IGNORECASE,
)


def forbidden_env_tokens(env: Environment) -> Tuple[str, ...]:
    if env == Environment.dev:
        return ("stage", "stg", "prod")
    if env == Environment.stage:
        return ("dev", "prod")
    return ("dev", "stage", "stg")


def find_foreign_env_token(val: str, env: Environment) -> Optional[str]:
    """Return forbidden env token if it appears in the value.

    Important: we intentionally avoid naive substring matching.

    Example of a common false positive (before 2026-02):
      "postgres" contains "stg" as a substring, which must NOT be treated
      as a reference to stage/stg environment.

    We match tokens as standalone "segments": they must not be surrounded by letters.
    Digits are allowed (e.g. stg1, dev2).
    """

    v = str(val).lower()
    for tok in forbidden_env_tokens(env):
        # Not preceded by a letter, not followed by a letter.
        # This matches:
        #   - "dev." / "-dev-" / "/dev/" / "dev1"
        # but does NOT match:
        #   - "developer" / "postgres" (stg inside)
        if re.search(rf"(?<![a-z]){re.escape(tok)}(?![a-z])", v):
            return tok
    return None
