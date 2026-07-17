from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..models import ConnectorType, Environment


@dataclass(frozen=True)
class DetectedLayout:
    """Best-effort parsing of connector naming convention into repo structure."""

    env: Environment
    domain: str
    connector_type: ConnectorType
    system: str
    connector_dir: str

    # Optional naming hints (mainly for sinks)
    dataset: Optional[str] = None
    layer: Optional[str] = None
    kind: str = "default"  # for sinks: default / events / flatten / custom
