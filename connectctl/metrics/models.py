from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class LocStats:
    files: int
    total_lines: int
    total_sloc: int
    min_lines: int
    min_path: str
    max_lines: int
    max_path: str
    avg_lines: float
    median_lines: float
    avg_sloc: float
    median_sloc: float
    top: List[Tuple[str, int, int]]


@dataclass(frozen=True)
class CouplingStats:
    """Сводка по графу import‑зависимостей внутри connectctl.*"""

    modules: int
    internal_edges: int
    avg_ce: float
    median_ce: float
    p90_ce: float
    p95_ce: float
    max_ce: int
    max_ce_module: str
    max_ca: int
    max_ca_module: str
    lcc_ratio: float
    avg_clustering: float
    cohesion_ratio: float
    top_out: List[Tuple[str, int]]
    top_in: List[Tuple[str, int]]
