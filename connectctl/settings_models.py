from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Tuple

from .config_models import ExportConfig, NamingConfig, SafetyConfig, SyncConfig
from .models import ConnectClusterConfig, Environment, RepoConfig
from .runtime_safety import RuntimeSafetyConfig


@dataclass(frozen=True)
class TagSettings:
    """Настройки тегов коннекторов.

    `definitions` — произвольное отображение `tag -> {param: value, ...}`.

    `hard_conflict_params` — список параметров, которые НИКОГДА не должны конфликтовать
    между тегами (даже если включён `--suppress-tag-conflicts`).

    Сейчас основной параметр — `cluster`.
    """

    definitions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    hard_conflict_params: Tuple[str, ...] = ("cluster",)


@dataclass(frozen=True)
class FunctionsSettings:
    """Repo-local placeholder function loading policy."""

    enabled: bool = True
    paths: Tuple[str, ...] = ("bkkt/functions",)
    allow_repo_python: bool = True
    runtime: RuntimeSafetyConfig = field(default_factory=RuntimeSafetyConfig)


@dataclass(frozen=True)
class ComputedVarsSettings:
    """Repo-local computed variable loading policy."""

    enabled: bool = True
    paths: Tuple[str, ...] = ("bkkt/computed_vars",)
    allow_repo_python: bool = True


@dataclass(frozen=True)
class VarProvidersSettings:
    """Repo-local variable provider loading policy."""

    enabled: bool = True
    paths: Tuple[str, ...] = ("bkkt/var_providers",)
    allow_repo_python: bool = True
    runtime: RuntimeSafetyConfig = field(default_factory=RuntimeSafetyConfig)


@dataclass(frozen=True)
class Settings:
    repo: RepoConfig

    # Backwards-compatible default cluster (env -> connect endpoints)
    clusters: Dict[Environment, ConnectClusterConfig]

    # Multi-cluster support: cluster_name -> (env -> connect endpoints)
    cluster_groups: Dict[str, Dict[Environment, ConnectClusterConfig]]

    # Name of the default cluster group.
    default_cluster: str

    # Optional tag configuration.
    tags: TagSettings

    naming: NamingConfig
    sync: SyncConfig
    safety: SafetyConfig
    export: ExportConfig
    functions: FunctionsSettings = field(default_factory=FunctionsSettings)
    computed_vars: ComputedVarsSettings = field(default_factory=ComputedVarsSettings)
    var_providers: VarProvidersSettings = field(default_factory=VarProvidersSettings)

    # Config tests (optional)
    config_tests: Dict[str, Any] = field(default_factory=dict)

    # Schema Registry preflight policy registry (optional)
    schema_registry_preflight: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def load(path: Path, repo_root: Path) -> "Settings":
        """Загрузить Settings из connectctl.yaml.

        Метод сохранён для обратной совместимости: исторически весь код вызывал
        `Settings.load(...)`. Реальная реализация находится в `settings_loader`.
        """

        # Import inside method to avoid circular imports.
        from .settings_loader import load_settings

        return load_settings(path, repo_root=repo_root)

    @staticmethod
    def empty(repo_root: Path) -> "Settings":
        """Build a minimal placeholder config for config-less CLI commands.

        This is intentionally conservative: commands that truly need cluster
        settings will still fail later with a clear configuration error.
        """

        return Settings(
            repo=RepoConfig(root=repo_root, connectors_root=repo_root),
            clusters={},
            cluster_groups={},
            default_cluster="default",
            tags=TagSettings(),
            naming=NamingConfig(),
            sync=SyncConfig(),
            safety=SafetyConfig(),
            export=ExportConfig(),
            functions=FunctionsSettings(),
            computed_vars=ComputedVarsSettings(),
            var_providers=VarProvidersSettings(),
            config_tests={},
            schema_registry_preflight={},
        )
