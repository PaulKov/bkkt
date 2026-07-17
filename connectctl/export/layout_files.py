from __future__ import annotations

from .layout_models import DetectedLayout
from ..models import ConnectorType


def build_sink_manifest_filename(layout: DetectedLayout, connector_name: str) -> str:
    """Dot-style: env manifest file name equals connector name."""
    if layout.connector_type != ConnectorType.sink:
        raise ValueError("layout must be sink")
    return f"{connector_name}.json"


def build_source_manifest_filename(connector_name: str) -> str:
    """Dot-style: env manifest file name equals connector name."""
    return f"{connector_name}.json"
