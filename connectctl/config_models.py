from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple


@dataclass(frozen=True)
class NamingRule:
    """A naming validation rule.

    A rule can be expressed either as:
      - template: a dot-delimited format string with placeholders (recommended)
      - regex: a python regex (optionally also a format string)

    The rule can be scoped using `applies_to`.

    Supported applies_to keys (case-sensitive values):
      - env: dev|stage|prod
      - domain: domain folder name
      - type: source|sink
      - system: postgres|mariadb|iceberg|...
      - layer: sink layer extracted from filename (e.g. ods)
      - mode: init|cdc (best-effort)
      - connector_dir: connector directory name
    """

    id: str
    template: Optional[str] = None
    regex: Optional[str] = None
    description: str = ""
    applies_to: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class NamingConfig:
    """Naming validation configuration."""

    enabled: bool = True
    strict: bool = True
    rules: Tuple[NamingRule, ...] = ()
    extra_allowed_patterns: Tuple[str, ...] = ()


@dataclass(frozen=True)
class PrunePolicy:
    """Deletion policy for `sync --prune`.

    The policy is evaluated in this order for an existing connector `name`:
      1) If name is in deny_names or matches any deny_regex -> NEVER delete
      2) If allow_* lists are non-empty:
           - delete only if name is in allow_names OR matches any allow_regex
         Else (allow lists empty):
           - delete is allowed (subject to deny)

    Note: desired connectors from the repo are never deleted.
    """

    allow_names: Tuple[str, ...] = ()
    deny_names: Tuple[str, ...] = ()
    allow_regex: Tuple[str, ...] = ()
    deny_regex: Tuple[str, ...] = ()


@dataclass(frozen=True)
class SyncConfig:
    prune: PrunePolicy = PrunePolicy()


@dataclass(frozen=True)
class ExportConfig:
    """Export behavior configuration."""

    auto_index_suffix_on_collision: bool = True


@dataclass(frozen=True)
class DirectPutConfig:
    """Safety policy for 'put-config' (direct PUT outside GitOps apply/sync).

    This is intentionally explicit, because PUT /connectors/{name}/config can change production
    state immediately.

    enabled:
      If false, `connectctl put-config` is disabled.

    allowed_envs:
      If non-empty, only these environments are allowed (e.g. ["dev"]).

    require_existing:
      If true, refuse to apply config if the connector doesn't already exist in the target Connect cluster.

    allow_create:
      If true, and require_existing is false, allow creating a connector when it does not exist.
      (This is still controlled by `enabled` + `allowed_envs`.)
    """

    enabled: bool = True
    allowed_envs: Tuple[str, ...] = ("dev",)
    require_existing: bool = True
    allow_create: bool = False


@dataclass(frozen=True)
class SafetyConfig:
    direct_put: DirectPutConfig = DirectPutConfig()
