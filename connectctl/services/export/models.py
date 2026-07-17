from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Pattern

from ...models import ConnectorType


@dataclass(frozen=True)
class ExportSelection:
    all: bool
    names: List[str]


@dataclass(frozen=True)
class ExportFilters:
    patterns: List[Pattern[str]]
    filter_type: Optional[ConnectorType]
    filter_domain: Optional[str]
    filter_system: Optional[str]

    def has_any(self) -> bool:
        return (
            bool(self.patterns)
            or bool(self.filter_type)
            or bool(self.filter_domain)
            or bool(self.filter_system)
        )


@dataclass(frozen=True)
class ExportPlacementOverrides:
    """Override placement for explicit names (NOT for --all filters)."""

    domain: Optional[str]
    connector_type: Optional[ConnectorType]
    system: Optional[str]
    connector_dir: Optional[str]


@dataclass(frozen=True)
class ExportFlags:
    dry_run: bool
    force: bool
    reuse_overrides: bool
    save_diffs: bool
    auto_index_suffix_on_collision: bool


@dataclass(frozen=True)
class ExportVariants:
    source_modes: List[str]
    sink_kinds: List[str]
    init_only: bool


@dataclass(frozen=True)
class IcebergScaffolding:
    kinds: List[str]
    generate_overrides: bool
    generate_manifests: bool
    table_id_columns: Dict[str, str]


@dataclass(frozen=True)
class ExportReuse:
    override_only_paths: Optional[List[Path]]


DOT_ENV_RE: Pattern[str] = re.compile(r"^(dev|stage|prod)\.", re.IGNORECASE)
