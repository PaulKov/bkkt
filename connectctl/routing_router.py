from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from .exceptions import ConfigError, TagConflictError
from .models import ConnectClusterConfig, Environment
from .settings import Settings

from .routing_models import RoutingDecision
from .routing_tags import norm_tag_list


class ClusterRouter:
    """Resolve a target Connect cluster for a connector.

    Routing inputs (in priority order):
      1) CLI override (--cluster)
      2) explicit manifest metadata: connectctl.cluster
      3) tag-derived params (tags.<tag>.cluster)
      4) global default: settings.default_cluster

    Tag conflicts:
      - If multiple tags set the same param to different values:
          * param in settings.tags.hard_conflict_params => ALWAYS ERROR
          * otherwise: error unless suppress_tag_conflicts=True
    """

    def __init__(
        self,
        *,
        settings: Settings,
        env: Environment,
        cli_cluster: Optional[str] = None,
        suppress_tag_conflicts: bool = False,
        logger: Optional[Callable[[str], None]] = None,
    ):
        self.settings = settings
        self.env = env
        self.cli_cluster = (cli_cluster or "").strip() or None
        self.suppress_tag_conflicts = bool(suppress_tag_conflicts)
        self.log = logger or (lambda msg: None)

    def get_cluster(self, cluster_name: str) -> ConnectClusterConfig:
        cluster_name = str(cluster_name).strip()
        if not cluster_name:
            raise ConfigError("Cluster name must not be empty")

        group = self.settings.cluster_groups.get(cluster_name)
        if group is None:
            raise ConfigError(
                f"Unknown cluster {cluster_name!r}. Available: {sorted(self.settings.cluster_groups.keys())}"
            )
        cfg = group.get(self.env)
        if cfg is None:
            raise ConfigError(
                f"Cluster {cluster_name!r} is not configured for env={self.env.value}. "
                f"Available envs: {sorted(e.value for e in group.keys())}"
            )
        return cfg

    def _collect_tag_assignments(
        self, tags: Sequence[str]
    ) -> Dict[str, List[Tuple[str, Any]]]:
        defs = self.settings.tags.definitions or {}

        assigns: Dict[str, List[Tuple[str, Any]]] = {}
        for tag in tags:
            cfg = defs.get(tag)
            if cfg is None:
                continue
            if not isinstance(cfg, Mapping):
                raise ConfigError(f"tags.definitions.{tag} must be a mapping")
            for param, value in cfg.items():
                assigns.setdefault(str(param), []).append((tag, value))
        return assigns

    def _resolve_tag_params(
        self, assigns: Dict[str, List[Tuple[str, Any]]], *, connector_name: str
    ) -> Dict[str, Any]:
        hard = set(self.settings.tags.hard_conflict_params or ())

        resolved: Dict[str, Any] = {}

        for param, items in assigns.items():
            uniq: List[Any] = []
            for _, v in items:
                if not any(v == u for u in uniq):
                    uniq.append(v)

            if len(uniq) <= 1:
                resolved[param] = items[-1][1]
                continue

            details = ", ".join(f"{t}={v!r}" for t, v in items)
            msg = f"Tag conflict for connector {connector_name}: param '{param}' has multiple values across tags: {details}"

            if param in hard:
                raise TagConflictError(msg)
            if not self.suppress_tag_conflicts:
                raise TagConflictError(msg)

            self.log(
                f"WARN: {msg} (suppressed; using value from last tag '{items[-1][0]}')"
            )
            resolved[param] = items[-1][1]

        return resolved

    def route(
        self,
        *,
        connector_name: str,
        connectctl_meta: Optional[Mapping[str, Any]] = None,
        connectctl_sources: Optional[Mapping[str, str]] = None,
    ) -> RoutingDecision:
        decision, _debug = self.route_with_debug(
            connector_name=connector_name,
            connectctl_meta=connectctl_meta,
            connectctl_sources=connectctl_sources,
        )
        return decision

    def route_with_debug(
        self,
        *,
        connector_name: str,
        connectctl_meta: Optional[Mapping[str, Any]] = None,
        connectctl_sources: Optional[Mapping[str, str]] = None,
    ) -> Tuple[RoutingDecision, Dict[str, Any]]:
        meta = dict(connectctl_meta or {})

        tags = norm_tag_list(meta.get("tags"))
        assigns = self._collect_tag_assignments(tags)
        tag_params = self._resolve_tag_params(assigns, connector_name=connector_name)

        explicit_cluster = str(meta.get("cluster") or "").strip() or None
        tag_cluster = str(tag_params.get("cluster") or "").strip() or None

        if self.cli_cluster:
            cluster_name = self.cli_cluster
            src = "cli"
        elif explicit_cluster:
            cluster_name = explicit_cluster
            src = "connectctl.cluster"
        elif tag_cluster:
            cluster_name = tag_cluster
            src = "tag"
        else:
            cluster_name = self.settings.default_cluster
            src = "default_cluster"

        cluster_cfg = self.get_cluster(cluster_name)

        debug: Dict[str, Any] = {
            "connector": connector_name,
            "env": self.env.value,
            "default_cluster": self.settings.default_cluster,
            "cli_cluster": self.cli_cluster,
            "connectctl_cluster": explicit_cluster,
            "connectctl_cluster_source": (connectctl_sources or {}).get("cluster"),
            "tags": tags,
            "tag_cluster_assignments": assigns.get("cluster", []),
            "selected_cluster": cluster_name,
            "selected_source": src,
        }

        c_items = assigns.get("cluster", []) or []
        uniq_vals: List[Any] = []
        for _t, v in c_items:
            if not any(v == u for u in uniq_vals):
                uniq_vals.append(v)
        if len(uniq_vals) > 1:
            debug["tag_cluster_conflict"] = ", ".join(f"{t}={v!r}" for t, v in c_items)

        return (
            RoutingDecision(cluster_name=cluster_name, cluster=cluster_cfg, source=src),
            debug,
        )
