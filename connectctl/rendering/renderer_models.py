from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..models import ConnectorManifest


@dataclass(frozen=True)
class VarUsage:
    key: str
    value: str
    source: str


@dataclass
class RenderResult:
    manifest: ConnectorManifest
    layers: Tuple[Path, ...]

    # Tool-specific metadata (not sent to Kafka Connect).
    # Comes from `connectctl`/`tags` keys in layer fragments.
    connectctl: Dict[str, Any] = field(default_factory=dict)

    # Provenance for connectctl meta keys (flattened), e.g. {"cluster": "connectctl:__global/source/prod.json"}
    connectctl_sources: Dict[str, str] = field(default_factory=dict)

    # Provenance for tags (each occurrence): (tag, source)
    tags_sources: Tuple[Tuple[str, str], ...] = ()

    # Diagnostics for where connector name comes from
    name_first_set_by: Optional[Path] = None
    name_last_set_by: Optional[Path] = None
    name_inferred_from_filename: bool = False

    # Vars that were actually substituted during placeholder resolution
    vars_used: Tuple[VarUsage, ...] = ()

    # Full placeholder context exposed for local diagnostics / functions CLI.
    placeholder_context: Dict[str, Any] = field(default_factory=dict)
    placeholder_sources: Dict[str, str] = field(default_factory=dict)

    # Context used to evaluate repo-local variable providers. This is captured
    # after layered/runtime vars and target metadata are known, but before
    # providers mutate the placeholder context. Apply-time preflight uses it to
    # validate provider contracts against the exact deploy context.
    provider_base_context: Dict[str, Any] = field(default_factory=dict)
    provider_base_sources: Dict[str, str] = field(default_factory=dict)
    provider_metadata: Dict[str, Any] = field(default_factory=dict)

    # Merged config before placeholder resolution. Diagnostics use it to explain
    # inherited/layered template values, not only placeholders from one env file.
    template_config: Dict[str, Any] = field(default_factory=dict)

    # Provenance for config leaf keys (flattened dot-keys)
    config_sources: Dict[str, str] = field(default_factory=dict)
    # Full chain of overrides for config leaf keys (low -> high priority)
    config_sources_chain: Dict[str, Tuple[str, ...]] = field(default_factory=dict)

    # Explicitly removed inherited keys (declared via bkkt.unset_config_keys).
    unset_config_keys: Tuple[str, ...] = ()
    unset_config_key_sources: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
