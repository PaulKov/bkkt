from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml

from .exceptions import ConfigError
from .models import RepoConfig
from .settings_clusters import parse_cluster_groups
from .settings_models import (
    ComputedVarsSettings,
    FunctionsSettings,
    Settings,
    VarProvidersSettings,
)
from .runtime_safety import RuntimeSafetyConfig
from .settings_parsers import (
    parse_export,
    parse_naming,
    parse_safety,
    parse_sync,
    parse_tags,
)
from .utils import expand_env_in_obj


def load_settings(path: Path, *, repo_root: Path) -> Settings:
    """Загрузить настройки из connectctl.yaml/json.

    Исторически входной точкой был `Settings.load(...)`. Этот helper позволяет
    вынести реальную реализацию из dataclass-модели.
    """

    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise ConfigError(f"Config file is empty: {path}")

    if path.suffix.lower() in {".yml", ".yaml"}:
        data = yaml.safe_load(raw) or {}
    elif path.suffix.lower() == ".json":
        data = json.loads(raw)
    else:
        raise ConfigError(
            f"Unsupported config format: {path.suffix}. Use YAML or JSON."
        )

    data = expand_env_in_obj(data)

    connectors_root = Path(str(data.get("connectors_root", ".")))
    ignore_dirs = tuple(data.get("ignore_dirs", [])) or RepoConfig.ignore_dirs

    repo_cfg = RepoConfig(
        root=repo_root,
        connectors_root=(repo_root / connectors_root).resolve(),
        ignore_dirs=ignore_dirs,
    )

    clusters_raw = data.get("clusters", {})
    if not isinstance(clusters_raw, Mapping) or not clusters_raw:
        raise ConfigError("Config must contain non-empty 'clusters' mapping")

    cluster_groups = parse_cluster_groups(
        clusters_raw,
        root_lifecycle_raw=data.get("cluster_lifecycle"),
    )

    default_cluster = str(
        data.get("default_cluster") or data.get("default_cluster_name") or ""
    ).strip()
    if not default_cluster:
        # For old format, default is "default". For new format, default is first cluster group.
        default_cluster = (
            "default"
            if "default" in cluster_groups
            else next(iter(cluster_groups.keys()))
        )

    if default_cluster not in cluster_groups:
        raise ConfigError(
            f"default_cluster={default_cluster!r} does not exist in clusters. Available: {sorted(cluster_groups.keys())}"
        )

    # Expose default cluster mapping under legacy Settings.clusters (env -> clusterconfig)
    clusters = dict(cluster_groups[default_cluster])

    # --- Tag configuration (optional)
    tags_obj = data.get("tags", {}) or {}
    tags = parse_tags(tags_obj)

    # --- Naming configuration (optional)
    naming_obj = data.get("naming", {}) or {}
    naming = parse_naming(naming_obj)

    # --- Sync/prune configuration (optional)
    sync_obj = data.get("sync", {}) or {}
    sync = parse_sync(sync_obj)

    # --- Safety configuration (optional)
    safety_obj = data.get("safety", {}) or {}
    safety = parse_safety(safety_obj)

    # --- Export configuration (optional)
    export_obj = data.get("export", {}) or {}
    export = parse_export(export_obj)

    # --- Repo-local functions configuration (optional)
    functions_obj = data.get("functions", {}) or {}
    functions = _parse_functions(functions_obj)

    # --- Repo-local computed variables configuration (optional)
    computed_vars_obj = data.get("computed_vars", {}) or {}
    computed_vars = _parse_computed_vars(computed_vars_obj)

    # --- Repo-local variable providers configuration (optional)
    var_providers_obj = data.get("var_providers", {}) or {}
    var_providers = _parse_var_providers(var_providers_obj)

    # --- Config tests configuration (optional)
    config_tests_obj = data.get("config_tests", {}) or {}
    config_tests: Dict[str, Any] = (
        config_tests_obj if isinstance(config_tests_obj, dict) else {}
    )

    # --- Schema Registry preflight configuration (optional)
    schema_registry_preflight_obj = data.get("schema_registry_preflight", {}) or {}
    schema_registry_preflight: Dict[str, Any] = (
        schema_registry_preflight_obj
        if isinstance(schema_registry_preflight_obj, dict)
        else {}
    )

    return Settings(
        repo=repo_cfg,
        clusters=clusters,
        cluster_groups=cluster_groups,
        default_cluster=default_cluster,
        tags=tags,
        naming=naming,
        sync=sync,
        safety=safety,
        export=export,
        functions=functions,
        computed_vars=computed_vars,
        var_providers=var_providers,
        config_tests=config_tests,
        schema_registry_preflight=schema_registry_preflight,
    )


def _parse_functions(obj: Any) -> FunctionsSettings:
    if obj is None:
        return FunctionsSettings()
    if not isinstance(obj, Mapping):
        raise ConfigError("'functions' must be a mapping")

    default_paths = FunctionsSettings().paths
    raw_paths = obj.get("paths", default_paths)
    paths: tuple[str, ...]
    if isinstance(raw_paths, str):
        paths = (raw_paths,)
    elif isinstance(raw_paths, list):
        paths = tuple(str(item) for item in raw_paths)
    elif isinstance(raw_paths, tuple):
        paths = tuple(str(item) for item in raw_paths)
    else:
        raise ConfigError("'functions.paths' must be a string or list of strings")

    return FunctionsSettings(
        enabled=bool(obj.get("enabled", True)),
        paths=paths or default_paths,
        allow_repo_python=bool(obj.get("allow_repo_python", True)),
        runtime=_parse_runtime_safety(obj.get("runtime", {}) or {}),
    )


def _parse_computed_vars(obj: Any) -> ComputedVarsSettings:
    if obj is None:
        return ComputedVarsSettings()
    if not isinstance(obj, Mapping):
        raise ConfigError("'computed_vars' must be a mapping")

    default_paths = ComputedVarsSettings().paths
    raw_paths = obj.get("paths", default_paths)
    paths: tuple[str, ...]
    if isinstance(raw_paths, str):
        paths = (raw_paths,)
    elif isinstance(raw_paths, list):
        paths = tuple(str(item) for item in raw_paths)
    elif isinstance(raw_paths, tuple):
        paths = tuple(str(item) for item in raw_paths)
    else:
        raise ConfigError("'computed_vars.paths' must be a string or list of strings")

    return ComputedVarsSettings(
        enabled=bool(obj.get("enabled", True)),
        paths=paths or default_paths,
        allow_repo_python=bool(obj.get("allow_repo_python", True)),
    )


def _parse_var_providers(obj: Any) -> VarProvidersSettings:
    if obj is None:
        return VarProvidersSettings()
    if not isinstance(obj, Mapping):
        raise ConfigError("'var_providers' must be a mapping")

    default_paths = VarProvidersSettings().paths
    raw_paths = obj.get("paths", default_paths)
    paths: tuple[str, ...]
    if isinstance(raw_paths, str):
        paths = (raw_paths,)
    elif isinstance(raw_paths, list):
        paths = tuple(str(item) for item in raw_paths)
    elif isinstance(raw_paths, tuple):
        paths = tuple(str(item) for item in raw_paths)
    else:
        raise ConfigError("'var_providers.paths' must be a string or list of strings")

    return VarProvidersSettings(
        enabled=bool(obj.get("enabled", True)),
        paths=paths or default_paths,
        allow_repo_python=bool(obj.get("allow_repo_python", True)),
        runtime=_parse_runtime_safety(obj.get("runtime", {}) or {}),
    )


def _parse_runtime_safety(obj: Any) -> RuntimeSafetyConfig:
    if obj is None:
        return RuntimeSafetyConfig()
    if not isinstance(obj, Mapping):
        raise ConfigError("'runtime' safety settings must be a mapping")

    raw_timeout = obj.get("max_call_ms", RuntimeSafetyConfig().max_call_ms)
    max_call_ms = None if raw_timeout is None else int(raw_timeout)

    raw_capabilities = obj.get("allowed_capabilities", ())
    capabilities: tuple[str, ...]
    if isinstance(raw_capabilities, str):
        capabilities = (raw_capabilities,)
    elif isinstance(raw_capabilities, list):
        capabilities = tuple(str(item) for item in raw_capabilities)
    elif isinstance(raw_capabilities, tuple):
        capabilities = tuple(str(item) for item in raw_capabilities)
    else:
        raise ConfigError(
            "'runtime.allowed_capabilities' must be a string or list of strings"
        )

    return RuntimeSafetyConfig(
        max_call_ms=max_call_ms,
        allowed_capabilities=tuple(
            item.strip() for item in capabilities if item.strip()
        ),
    )
