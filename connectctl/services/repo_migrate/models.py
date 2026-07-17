from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ConnectorDirInfo:
    domain: str
    connector_type: str  # source|sink
    system: str
    name: str
    rel_path: Path  # relative to connectors_root
    abs_path: Path  # absolute path on FS (or best-effort)


@dataclass(frozen=True)
class RenamePlanItem:
    info: ConnectorDirInfo
    suggested_name: Optional[str]
    suggested_rel_path: Optional[Path]
    reason: str
    conflict: bool = False
    conflict_with: Optional[Path] = None
    manual: bool = False


@dataclass(frozen=True)
class ReferenceUpdateResult:
    updated_files: int
    touched_paths: list[str]


@dataclass(frozen=True)
class MigrationResult:
    total_scanned: int
    violations: int
    actionable: int
    manual: int
    conflicts: int
    applied: int
    skipped: int
    reference_updates: Optional[ReferenceUpdateResult] = None
