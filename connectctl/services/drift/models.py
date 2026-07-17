from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class DriftOptions:
    """Опции для построения drift-отчёта."""

    include_diffs: bool
    max_lines: int
    top_n: int
    strict_naming: bool
    policies: bool
    fail_on_drift: bool


@dataclass
class DriftCollected:
    """Агрегированные результаты сравнения repo ↔ live."""

    manifests_checked: int
    ok_count: int
    disabled_skipped: int
    drift_count: int
    missing_count: int

    # Summary группировки
    group_stats_dt: Dict[str, Dict[str, int]]
    group_stats_dts: Dict[str, Dict[str, int]]

    # Top причины
    drift_key_counter: Counter[str]
    drift_override_source_counter: Counter[str]

    # Детали
    detailed: List[Dict[str, object]]
