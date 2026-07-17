from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Optional

from ..app.context import CliContext
from ..cli_helpers.routing_explain import format_routing_explain_lines
from ..lifecycle.guards import log_disabled_manifest_skip
from ..logging_utils import get_logger
from ..rendering.factory import build_renderer
from ..rendering.explain_config import log_config_key_sources
from ..rendering.renderer_infer import (
    infer_dataset_from_connector_dir,
    infer_dataset_from_name,
)
from ..rendering.runtime_vars import load_runtime_vars_with_sources, log_vars_used
from ..repo import ConnectorRepo
from ..routing import ClusterRouter, format_cluster_target


@dataclass
class InspectService:
    """Сервис для `connectctl inspect`.

    Показывает:
    - как распарсился путь манифеста (env/domain/type/system/connector_dir/mode/kind…)
    - как отрендерился финальный manifest (name/config) с учётом слоёв
    - куда *будет* роутиться коннектор (cluster group + env + urls) и почему

    NOTE: `dataset` не является частью :class:`connectctl.models.ConnectorPathInfo`.
    Dataset используется как удобная переменная в шаблонах (placeholders) и
    выводится здесь как *derived* значение (из имени коннектора или connector_dir).
    """

    ctx: CliContext
    logger: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        self.log = get_logger(self.logger or self.ctx.logger)

    def run(self, args) -> int:
        repo_root = self.ctx.repo_root
        settings = self.ctx.settings

        p = (repo_root / str(getattr(args, "path"))).resolve()

        repo = ConnectorRepo(settings.repo, fs=self.ctx.fs)
        info = repo.parse_connector_path(p, must_exist=True)

        renderer = build_renderer(
            settings,
            fs=self.ctx.fs,
            routing_cli_cluster=getattr(args, "cluster", None),
            routing_suppress_tag_conflicts=bool(
                getattr(args, "suppress_tag_conflicts", False)
            ),
        )
        runtime_vars, runtime_sources = load_runtime_vars_with_sources(args, repo_root)

        rr = renderer.render(
            p, runtime_vars=runtime_vars, runtime_var_sources=runtime_sources
        )
        if rr.manifest.lifecycle.disabled:
            log_disabled_manifest_skip(
                manifest=rr.manifest,
                logger=self.log,
                repo_root=repo_root,
                action="WARN",
            )

        # Derived dataset (best-effort)
        ds_from_name = infer_dataset_from_name(rr.manifest.name, info.env.value)
        ds = ds_from_name or infer_dataset_from_connector_dir(info.connector_dir)
        ds_src = "connector.name" if ds_from_name else "connector_dir"

        self.log.info("Connector file: %s", info.relpath)
        self.log.info("Env: %s", info.env.value)
        self.log.info("Domain: %s", info.domain)
        self.log.info("Dataset (derived): %s (from %s)", ds or "(not detected)", ds_src)
        self.log.info("Type: %s", info.connector_type.value)
        self.log.info("System: %s", info.system)
        self.log.info("Connector dir: %s", info.connector_dir)
        self.log.info("Mode: %s", info.mode or "(not detected)")

        if info.connector_type.value == "sink":
            self.log.info("Sink kind: %s", info.variant or "default")

        self.log.info("Rendered name: %s", rr.manifest.name)

        # Routing
        suppress = bool(getattr(args, "suppress_tag_conflicts", False))
        cli_cluster = getattr(args, "cluster", None)

        router = ClusterRouter(
            settings=settings,
            env=info.env,
            cli_cluster=cli_cluster,
            suppress_tag_conflicts=suppress,
            logger=lambda msg: self.log.warning("%s", msg),
        )

        decision, debug = router.route_with_debug(
            connector_name=rr.manifest.name,
            connectctl_meta=rr.connectctl,
            connectctl_sources=getattr(rr, "connectctl_sources", None),
        )

        self.log.info("Target cluster: %s", format_cluster_target(decision.cluster))
        self.log.info("Cluster group name: %s", decision.cluster_name)
        self.log.info("Routing source: %s", decision.source)

        if bool(getattr(args, "explain_routing", False)):
            for line in format_routing_explain_lines(debug):
                self.log.info("%s", line)

        if bool(getattr(args, "show_vars", True)):
            log_vars_used(rr, repo_root, logger=self.log)

        if bool(getattr(args, "explain_vars", False)):
            log_config_key_sources(
                rr,
                repo_root,
                keys_filter=getattr(args, "explain_vars_keys", None),
                max_rows=int(getattr(args, "explain_vars_max", 200) or 0),
                logger=self.log,
            )

        if bool(getattr(args, "show_layers", False)):
            self.log.info("Layers (low -> high priority):")
            for lp in rr.layers:
                try:
                    rel = lp.relative_to(repo_root)
                except Exception:
                    rel = lp
                self.log.info(" - %s", rel)

        return 0
