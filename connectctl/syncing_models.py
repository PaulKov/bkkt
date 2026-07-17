from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .models import ConnectorManifest, Environment


@dataclass(frozen=True)
class SyncPlan:
    env: Environment
    desired: Dict[str, ConnectorManifest]
    desired_names: List[str]
    existing_names: List[str]
    protected_names: tuple[str, ...]
    to_apply: tuple[str, ...]
    to_delete: tuple[str, ...]


@dataclass(frozen=True)
class PrunePolicy:
    """Prune policy (legacy).

    NOTE: Kept for backward compatibility.
    The actual sync pruning policy used by settings lives in :class:`connectctl.config_models.PrunePolicy`.
    """

    allow_names: List[str]
    deny_names: List[str]
    allow_regexes: List[str]
    deny_regexes: List[str]
