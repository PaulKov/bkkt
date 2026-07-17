from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Optional

from ..app.context import CliContext
from ..lifecycle.guards import log_disabled_manifest_skip
from ..rendering.factory import build_renderer
from ..rendering.explain_config import log_config_key_sources
from ..rendering.runtime_vars import load_runtime_vars_with_sources, log_vars_used
from ..rendering.prune import apply_prune_to_render_result
from ..cli_helpers.routing_explain import format_routing_explain_lines
from ..logging_utils import get_logger
from ..output import OutputFormat, dumps_payload, resolve_output_format, write_payload
from ..routing import ClusterRouter, format_cluster_target


@dataclass
class RenderService:
    """Сервис `connectctl render`.

    Рендерит финальный manifest (name+config) с учётом слоёв и подстановок.
    """

    ctx: CliContext
    logger: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        self.log = get_logger(self.logger or self.ctx.logger)

    def run(self, args) -> int:
        repo_root = self.ctx.repo_root
        settings = self.ctx.settings

        renderer = build_renderer(
            settings,
            fs=self.ctx.fs,
            routing_cli_cluster=getattr(args, "cluster", None),
            routing_suppress_tag_conflicts=bool(
                getattr(args, "suppress_tag_conflicts", False)
            ),
        )
        env_file = (repo_root / str(getattr(args, "path"))).resolve()

        runtime_vars, runtime_sources = load_runtime_vars_with_sources(args, repo_root)

        reuse_overrides = bool(getattr(args, "reuse_overrides", True))
        reuse_from_raw = getattr(args, "reuse_from", None) or []
        reuse_from = [Path(p) for p in reuse_from_raw] or None

        rr = renderer.render(
            env_file,
            runtime_vars=runtime_vars,
            runtime_var_sources=runtime_sources,
            reuse_overrides=reuse_overrides,
            reuse_from=reuse_from,
        )
        if rr.manifest.lifecycle.disabled:
            log_disabled_manifest_skip(
                manifest=rr.manifest,
                logger=self.log,
                repo_root=repo_root,
                action="WARN",
            )

        # Resolve target cluster (used both for explain-routing and for cluster render policies).
        router = ClusterRouter(
            settings=settings,
            env=rr.manifest.info.env,
            cli_cluster=getattr(args, "cluster", None),
            suppress_tag_conflicts=bool(getattr(args, "suppress_tag_conflicts", False)),
            logger=lambda msg: self.log.warning("%s", msg),
        )
        decision, routing_debug = router.route_with_debug(
            connector_name=rr.manifest.name,
            connectctl_meta=rr.connectctl,
            connectctl_sources=rr.connectctl_sources,
        )

        # Apply cluster render policy (config pruning), if configured.
        pruned_keys: tuple[str, ...] = ()
        if decision.cluster.render_prune_config_keys:
            rr, pruned_keys = apply_prune_to_render_result(
                rr, decision.cluster.render_prune_config_keys
            )
            if pruned_keys:
                self.log.info(
                    "Cluster render policy: pruned %d config keys for %s",
                    len(pruned_keys),
                    format_cluster_target(decision.cluster),
                )

        payload = {"name": rr.manifest.name, "config": rr.manifest.config}

        fmt = resolve_output_format(args, default=OutputFormat.json)
        # Для render "text" = "json" (самый удобный человеко‑читаемый формат).
        if fmt == OutputFormat.text:
            fmt = OutputFormat.json

        out_path = getattr(args, "output_file", None)
        if out_path:
            out = Path(out_path).resolve()
            self.ctx.fs.write_text(
                out, dumps_payload(payload, fmt=fmt), encoding="utf-8"
            )
            self.log.info("Render written to: %s", out)

        # Основной результат — в stdout.
        write_payload(payload, fmt=fmt)

        if bool(getattr(args, "explain_routing", False)):
            self.log.info(
                "Target cluster (routing): %s", format_cluster_target(decision.cluster)
            )
            for line in format_routing_explain_lines(routing_debug):
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

            def _rel(p):
                if p is None:
                    return None
                try:
                    return p.relative_to(repo_root)
                except Exception:
                    return p

            if getattr(rr, "name_inferred_from_filename", False):
                self.log.info("Name source: inferred from filename")
            else:
                first = _rel(getattr(rr, "name_first_set_by", None))
                last = _rel(getattr(rr, "name_last_set_by", None))
                if first:
                    self.log.info("Name first set by: %s", first)
                    if last and last != first:
                        self.log.info("Name last set by:  %s", last)
                else:
                    self.log.info("Name source: unknown")

        return 0
