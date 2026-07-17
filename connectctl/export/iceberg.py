"""Iceberg helpers (публичный фасад).

Реальная логика разнесена по SRP-модулям:

- :mod:`connectctl.export.iceberg_single`
- :mod:`connectctl.export.iceberg_variants`
- :mod:`connectctl.export.iceberg_base`

Файл сохранён ради обратной совместимости импортов.
"""

from __future__ import annotations

from .iceberg_single import build_iceberg_sink_planned_files
from .iceberg_variants import build_iceberg_sink_variants_planned_files


__all__ = [
    "build_iceberg_sink_planned_files",
    "build_iceberg_sink_variants_planned_files",
]
