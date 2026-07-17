from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, TYPE_CHECKING

from ..exceptions import ConfigError
from ..logging_utils import get_logger
from ..models import ConnectorManifest, Environment
from ..rendering import ConnectorRenderer
from ..settings import Settings
from ..settings_clusters_lifecycle import disabled_cluster_message
from ..validation import ConfigTestRunner

if TYPE_CHECKING:
    from ..config_models import NamingConfig


DEFAULT_CONFIG_PATHS = (
    "connectctl.yaml",
    "ci/config/clusters.yaml",
)


def _find_config_path(repo_root: Path) -> Path:
    env_path = os.environ.get("CONNECTCTL_CONFIG", "").strip()
    if env_path:
        return (
            (repo_root / env_path).resolve()
            if not Path(env_path).is_absolute()
            else Path(env_path)
        )

    for p in DEFAULT_CONFIG_PATHS:
        cand = (repo_root / p).resolve()
        if cand.exists():
            return cand
    raise ConfigError(
        "Config file not found. Create connectctl.yaml (recommended) or set CONNECTCTL_CONFIG env var."
    )


def _build_renderer(settings: Settings) -> ConnectorRenderer:
    """Backwards-compatible wrapper for renderer construction.

    Новому коду лучше использовать `connectctl.rendering.factory.build_renderer`.
    """

    from ..rendering.factory import build_renderer

    return build_renderer(settings)


def _resolve_cluster_from_args(
    settings: Settings, env: Environment, cluster_name: Optional[str]
) -> Any:
    name = (cluster_name or settings.default_cluster or "default").strip()
    if name not in settings.cluster_groups:
        raise ConfigError(
            f"Unknown cluster group: {name!r}. Available: {sorted(settings.cluster_groups.keys())}"
        )
    env_map = settings.cluster_groups[name]
    if env not in env_map:
        raise ConfigError(
            f"Cluster group {name!r} has no env={env.value}. Available envs: {[e.value for e in env_map.keys()]}"
        )
    cluster = env_map[env]
    lifecycle = getattr(cluster, "lifecycle", None)
    if lifecycle is not None and getattr(lifecycle, "disabled", False):
        raise ConfigError(
            disabled_cluster_message(cluster=name, env=env.value, lifecycle=lifecycle)
        )
    return cluster


def _print_cluster_banner(cluster: Any, env: Environment, *, logger=None) -> None:
    log = get_logger(logger)
    urls = ", ".join(getattr(cluster, "urls", []) or [])
    log.info(
        "Cluster: %s env=%s urls=[%s]",
        getattr(cluster, "name", "default"),
        env.value,
        urls,
    )
    log.info("-" * 80)


def _validate_manifest(
    manifest: "ConnectorManifest",
    *,
    strict_naming: bool = False,
    policies: bool = False,
    policy_env: Optional[Environment] = None,
    policy_layers: Optional[Sequence[Path]] = None,
    config_test_runner: Optional["ConfigTestRunner"] = None,
    config_test_context: Optional[Mapping[str, Any]] = None,
    naming: Optional["NamingConfig"] = None,
    logger=None,
) -> None:
    """Backwards-compatible wrapper for manifest validation.

    Новому коду лучше использовать `connectctl.validation.manifest_validation.validate_manifest`.
    """

    from ..validation.manifest_validation import validate_manifest

    validate_manifest(
        manifest,
        strict_naming=strict_naming,
        policies=policies,
        policy_env=policy_env,
        policy_layers=policy_layers,
        config_test_runner=config_test_runner,
        config_test_context=config_test_context,
        naming=naming,
        logger=logger,
    )
