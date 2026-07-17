from __future__ import annotations

from typing import Optional

from ...exporting import DetectedLayout, autodetect_layout_from_name
from .models import ExportFilters, ExportPlacementOverrides


def resolve_layout(
    *,
    env,
    name: str,
    selection_all: bool,
    placement_overrides: ExportPlacementOverrides,
    log,
) -> Optional[DetectedLayout]:
    layout = autodetect_layout_from_name(name)
    if layout is None:
        # Manual fallback if autodetect failed and user provided explicit target structure.
        if (
            placement_overrides.domain
            and placement_overrides.connector_type
            and placement_overrides.system
            and placement_overrides.connector_dir
        ):
            return DetectedLayout(
                env=env,
                domain=str(placement_overrides.domain),
                connector_type=placement_overrides.connector_type,
                system=str(placement_overrides.system),
                connector_dir=str(placement_overrides.connector_dir),
            )

        log.warning("skip (cannot autodetect layout): %s", name)
        return None

    # If not --all, allow overriding placement with explicit args (optional).
    if not selection_all:
        # Keep original env from detected layout.
        if placement_overrides.domain:
            layout = DetectedLayout(
                **{**layout.__dict__, "domain": str(placement_overrides.domain)}
            )
        if placement_overrides.connector_type:
            layout = DetectedLayout(
                **{
                    **layout.__dict__,
                    "connector_type": placement_overrides.connector_type,
                }
            )
        if placement_overrides.system:
            layout = DetectedLayout(
                **{**layout.__dict__, "system": str(placement_overrides.system)}
            )
        if placement_overrides.connector_dir:
            layout = DetectedLayout(
                **{
                    **layout.__dict__,
                    "connector_dir": str(placement_overrides.connector_dir),
                }
            )

    return layout


def passes_all_filters(*, layout: DetectedLayout, filters: ExportFilters) -> bool:
    if filters.filter_type and layout.connector_type != filters.filter_type:
        return False
    if filters.filter_domain and layout.domain != filters.filter_domain:
        return False
    if filters.filter_system and layout.system != filters.filter_system:
        return False
    return True
