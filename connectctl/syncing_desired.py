from __future__ import annotations

from typing import List, Optional

from .models import ConnectorManifest, Environment
from .rendering.renderer import ConnectorRenderer
from .repo import ConnectorRepo


def build_desired_manifests(
    env: Environment,
    *,
    repo: ConnectorRepo,
    renderer: ConnectorRenderer,
    runtime_vars: Optional[dict] = None,
) -> List[ConnectorManifest]:
    """Render and collect all deployable manifests for the environment."""

    manifests: List[ConnectorManifest] = []
    for env_file in repo.iter_deployable_manifests(env):
        rr = renderer.render(env_file, runtime_vars=runtime_vars)
        manifests.append(rr.manifest)
    return manifests
