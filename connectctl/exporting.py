"""Экспорт коннекторов (фасад).

Исторически проект держал всю логику экспорта в одном большом модуле
`connectctl.exporting`.

На этапе рефакторинга v3 код разнесён по небольшим модулям в пакете
`connectctl.export` (layout/filters/virtual_render/iceberg/planner), но
этот модуль оставлен как **стабильный фасад** для обратной совместимости:

- команды и тесты продолжают делать `from connectctl.exporting import ...`
- внутренняя структура может меняться без массовых правок импортов
"""

from __future__ import annotations

# Layout autodetect + naming helpers
from .export.layout import (
    DetectedLayout,
    autodetect_layout_from_name,
    build_sink_manifest_filename,
    build_source_manifest_filename,
    resolve_sink_export_collision,
)

# Regex filters
from .export.filters import matches_any_regexp

# Virtual render (export preview)
from .export.virtual_render import (
    render_virtual,
    render_virtual_with_sources,
    resolve_layers_virtual,
)

# Iceberg sink scaffolding
from .export.iceberg import (
    build_iceberg_sink_planned_files,
    build_iceberg_sink_variants_planned_files,
)

# Export planning + repo materialization
from .export.planner import (
    apply_plan_to_repo,
    build_generic_planned_files,
    compute_delta_for_remote_keys,
    export_connector_to_repo,
)

__all__ = [
    # Layout
    "DetectedLayout",
    "autodetect_layout_from_name",
    "build_sink_manifest_filename",
    "build_source_manifest_filename",
    "resolve_sink_export_collision",
    # Filters
    "matches_any_regexp",
    # Virtual render
    "render_virtual",
    "render_virtual_with_sources",
    "resolve_layers_virtual",
    # Iceberg
    "build_iceberg_sink_planned_files",
    "build_iceberg_sink_variants_planned_files",
    # Planner
    "apply_plan_to_repo",
    "build_generic_planned_files",
    "compute_delta_for_remote_keys",
    "export_connector_to_repo",
]
