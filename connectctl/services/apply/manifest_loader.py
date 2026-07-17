from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from ...exceptions import ConfigError
from ...logging_utils import get_logger
from ...models import ConnectorManifest
from ...repo import ConnectorRepo
from ...repo.apply_targets import ApplyItem
from ...utils import deep_merge
from ...rendering import ConnectorRenderer
from ...rendering.runtime_vars import log_vars_used
from ...var_providers import VarProviderContext

from .artifacts import RenderedArtifactLoader


@dataclass(frozen=True)
class LoadedManifest:
    manifest: ConnectorManifest
    layers: Optional[Sequence[Path]]
    loaded_from_artifact: bool
    connectctl: Dict[str, Any]
    connectctl_sources: Dict[str, str]
    unset_config_keys: tuple[str, ...] = ()
    provider_context: Optional[VarProviderContext] = None


def load_manifest_for_item(
    *,
    item: ApplyItem,
    manifest_path: Path,
    repo_root: Path,
    repo: ConnectorRepo,
    renderer: ConnectorRenderer,
    runtime_vars: Dict[str, Any],
    runtime_var_sources: Dict[str, str],
    reuse_overrides: bool,
    reuse_from: Optional[Sequence[Path]],
    artifact_loader: Optional[RenderedArtifactLoader],
    show_vars: bool,
    logger=None,
) -> LoadedManifest:
    """Load manifest for an apply item.

    If artifact_loader is provided and has an artifact for this manifest_path,
    load it. Otherwise render the manifest from repo sources.
    """

    log = get_logger(logger)

    # 1) Artifact-based deploy (optional)
    if artifact_loader is not None:
        art = artifact_loader.try_load(manifest_path)
        if art is not None:
            return LoadedManifest(
                manifest=art.manifest,
                layers=None,
                loaded_from_artifact=True,
                connectctl=art.connectctl,
                connectctl_sources={},
                unset_config_keys=(),
                provider_context=None,
            )

        if artifact_loader.strict:
            try:
                relp = manifest_path.resolve().relative_to(repo_root)
            except Exception:
                relp = manifest_path
            raise ConfigError(
                f"Artifact-based deploy is enabled (--from-rendered) but rendered artifact is missing for {relp}. "
                "Re-run 'connectctl render-changed' (or disable --artifact-strict / --from-rendered)."
            )

    # 2) Normal render
    merged_runtime = deep_merge(runtime_vars, item.runtime_vars)
    merged_sources = dict(runtime_var_sources)
    merged_sources.update(item.runtime_var_sources or {})

    rr = renderer.render(
        manifest_path,
        runtime_vars=merged_runtime,
        requested_path=item.requested_path,
        runtime_var_sources=merged_sources,
        reuse_overrides=reuse_overrides,
        reuse_from=list(reuse_from) if reuse_from else None,
    )

    if show_vars:
        log_vars_used(rr, repo_root, logger=log)

    return LoadedManifest(
        manifest=rr.manifest,
        layers=rr.layers,
        loaded_from_artifact=False,
        connectctl=rr.connectctl,
        connectctl_sources=rr.connectctl_sources,
        unset_config_keys=rr.unset_config_keys,
        provider_context=VarProviderContext.from_flat_context(
            rr.provider_base_context,
            sources=rr.provider_base_sources,
            repo_root=repo_root,
            manifest_path=manifest_path,
            metadata=rr.provider_metadata,
        ),
    )
