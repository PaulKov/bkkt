from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

from ..adapters.filesystem import LocalFileSystem
from ..cli_support import (
    _find_config_path,
    _print_cluster_banner,
    _resolve_cluster_from_args,
)
from ..connect import ConnectClient
from ..exceptions import ConfigError
from ..logging_utils import get_logger
from ..models import ConnectClusterConfig, Environment
from ..ports import ConnectApi, FileSystem
from ..settings import Settings


@dataclass(frozen=True)
class ConnectTarget:
    """Resolved target for Kafka Connect REST operations."""

    env: Environment
    cluster: ConnectClusterConfig
    client: ConnectApi


@dataclass
class CliContext:
    """DI-friendly context shared by CLI commands.

    Этот объект — "composition root" для CLI:
    - загружает Settings один раз
    - кеширует ConnectApi по (cluster_group, env)
    - содержит FileSystem (для тестируемости сервисов без диска)

    Сервисы должны зависеть от портов (Protocol), а реальные реализации
    подключаются здесь.
    """

    repo_root: Path
    config_path: Path
    settings: Settings
    logger: logging.Logger
    fs: FileSystem = field(default_factory=LocalFileSystem)

    _connect_cache: Dict[Tuple[str, Environment], ConnectApi] = field(
        default_factory=dict, init=False, repr=False
    )
    _cluster_cache: Dict[Tuple[str, Environment], ConnectClusterConfig] = field(
        default_factory=dict, init=False, repr=False
    )

    @classmethod
    def from_args(
        cls,
        args,
        *,
        logger: Optional[logging.Logger] = None,
        require_config: bool = True,
    ) -> "CliContext":
        """Build context from parsed CLI args."""

        log = get_logger(logger)

        repo_root = Path(getattr(args, "repo_root", ".")).resolve()
        cfg_arg = getattr(args, "config", None)
        cfg_path: Path | None = Path(cfg_arg).resolve() if cfg_arg else None

        if cfg_path is None:
            try:
                cfg_path = _find_config_path(repo_root)
            except ConfigError:
                if require_config:
                    raise
                cfg_path = repo_root / "connectctl.yaml"

        if cfg_path.exists():
            settings = Settings.load(cfg_path, repo_root=repo_root)
        elif require_config:
            raise ConfigError(
                "Config file not found. Create connectctl.yaml (recommended) or set CONNECTCTL_CONFIG env var."
            )
        else:
            settings = Settings.empty(repo_root)

        return cls(
            repo_root=repo_root,
            config_path=cfg_path,
            settings=settings,
            logger=log,
            fs=LocalFileSystem(),
        )

    def env(self, env_str: str) -> Environment:
        return Environment.from_str(str(env_str).strip().lower())

    def resolve_cluster(
        self, env: Environment, cluster_name: Optional[str]
    ) -> ConnectClusterConfig:
        name = (cluster_name or self.settings.default_cluster or "default").strip()
        key = (name, env)
        if key in self._cluster_cache:
            return self._cluster_cache[key]
        cluster = _resolve_cluster_from_args(self.settings, env, cluster_name)
        self._cluster_cache[key] = cluster
        return cluster

    def connect_api(
        self,
        env: Environment,
        cluster_name: Optional[str],
        *,
        throttle=None,
        timeout=None,
    ) -> ConnectApi:
        """Вернуть ConnectApi (Kafka Connect REST клиент) для заданного env/cluster."""

        cluster = self.resolve_cluster(env, cluster_name)
        key = (cluster.name, env)
        # Cache only non-throttled and default-timeout clients (common case).
        if throttle is None and timeout is None and key in self._connect_cache:
            return self._connect_cache[key]

        # В проде ConnectApi реализуется ConnectClient.
        if not cluster.urls:
            raise ConfigError(
                f"`{cluster.name}` / `{env.value}` runtime.type={cluster.runtime.type!r} "
                "does not expose Kafka Connect REST URLs. Configure runtime.rest "
                "access (for diagnostics) or use the runtime CRD/provider workflow."
            )
        kwargs = {"logger": self.logger, "throttle": throttle}
        if timeout is not None:
            kwargs["timeout"] = timeout

        api: ConnectApi = ConnectClient(cluster.urls, **kwargs)
        if throttle is None and timeout is None:
            self._connect_cache[key] = api
        return api

    def assert_rest_mutation_allowed(
        self,
        env: Environment,
        cluster_name: Optional[str],
        *,
        command: str,
        unsafe: bool = False,
    ) -> None:
        """Guard REST write operations for operator-managed runtimes.

        Strimzi/CFK reconcile connector CRDs back to desired state. A raw
        Kafka Connect REST mutation may be reverted or create split-brain
        GitOps/CRD drift, so BKKT blocks it unless the operator explicitly
        chooses break-glass mode.
        """

        cluster = self.resolve_cluster(env, cluster_name)
        if cluster.runtime.allows_rest_mutation or unsafe:
            return
        raise ConfigError(
            f"{command} would mutate Kafka Connect through REST, but "
            f"`{cluster.name}` / `{env.value}` uses runtime.type={cluster.runtime.type!r} "
            f"with mutation_mode={cluster.runtime.mutation_mode!r}. "
            "Use the runtime CRD/GitOps flow, or pass --runtime-unsafe-rest "
            "only for an explicit break-glass operation."
        )

    # Backward-compatible alias.
    def connect_client(
        self,
        env: Environment,
        cluster_name: Optional[str],
        *,
        throttle=None,
        timeout=None,
    ) -> ConnectApi:
        return self.connect_api(env, cluster_name, throttle=throttle, timeout=timeout)

    def connect_target(
        self,
        env: Environment,
        cluster_name: Optional[str],
        *,
        throttle=None,
        timeout=None,
    ) -> ConnectTarget:
        cluster = self.resolve_cluster(env, cluster_name)
        client = self.connect_api(env, cluster_name, throttle=throttle, timeout=timeout)
        return ConnectTarget(env=env, cluster=cluster, client=client)

    def print_cluster_banner(self, target: ConnectTarget) -> None:
        _print_cluster_banner(target.cluster, target.env, logger=self.logger)
