from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, List

from ..computed_vars import ComputedVarContext, ComputedVarRuntime
from ..exceptions import RenderError
from ..models import ConnectorManifest, ConnectorPathInfo
from ..repo import ConnectorRepo, LayerResolver
from ..routing import ClusterRouter
from ..settings_models import Settings
from ..template_runtime import FunctionContext, TemplateRuntime
from ..var_providers import VarProviderContext, VarProviderRuntime
from ..utils import deep_merge, flatten_dict
from .renderer_context import build_flat_placeholder_context
from .renderer_layers import merge_layer_fragments
from .renderer_models import RenderResult
from .renderer_name import guard_against_cyclic_name_reference, infer_name_from_filename
from .renderer_placeholders import resolve_rendered_name_and_config
from .renderer_tags import dedup_tags
from .renderer_target_context import build_target_context
from .renderer_vars_used import build_vars_used


class ConnectorRenderer:
    """Render connector manifests using layered override JSON files."""

    def __init__(
        self,
        repo: ConnectorRepo,
        layers: LayerResolver,
        *,
        settings: Optional[Settings] = None,
        routing_cli_cluster: Optional[str] = None,
        routing_suppress_tag_conflicts: bool = False,
        template_runtime: Optional[TemplateRuntime] = None,
    ):
        self.repo = repo
        self.layers = layers
        self.settings = settings
        self.routing_cli_cluster = routing_cli_cluster
        self.routing_suppress_tag_conflicts = bool(routing_suppress_tag_conflicts)
        self.template_runtime = template_runtime or TemplateRuntime.builtins_only()

    def render(
        self,
        env_file: Path,
        runtime_vars: Optional[Mapping[str, Any]] = None,
        *,
        requested_path: Optional[Path] = None,
        runtime_var_sources: Optional[Mapping[str, str]] = None,
        reuse_overrides: bool = True,
        reuse_from: Optional[Sequence[Path]] = None,
        routing_cli_cluster: Optional[str] = None,
        routing_suppress_tag_conflicts: Optional[bool] = None,
    ) -> RenderResult:
        requested_path = requested_path or env_file

        # Parse metadata primarily from requested_path (may be virtual), while keeping actual env_file for layers.
        info: ConnectorPathInfo = self.repo.parse_connector_path(
            requested_path, must_exist=False
        )
        base_file = self.repo.find_base_file_for(requested_path)
        layer_paths = self.layers.resolve(
            info=info,
            base_file=base_file,
            env_file=env_file,
            reuse_overrides=reuse_overrides,
            reuse_from=reuse_from,
        )

        merge = merge_layer_fragments(
            layer_paths, repo_root=self.repo.cfg.root, fs=self.repo.fs
        )
        name = merge.name
        config: Dict[str, Any] = dict(merge.config)
        config_sources: Dict[str, str] = dict(
            getattr(merge, "config_sources", {}) or {}
        )
        config_sources_chain = dict(getattr(merge, "config_sources_chain", {}) or {})
        vars_ctx: Dict[str, Any] = dict(merge.vars_ctx)
        vars_sources: Dict[str, str] = dict(merge.vars_sources)
        connectctl_meta: Dict[str, Any] = dict(merge.connectctl_meta)
        tags: List[str] = list(merge.tags)
        name_first_set_by = merge.name_first_set_by
        name_last_set_by = merge.name_last_set_by
        lifecycle = merge.lifecycle

        name_inferred_from_filename = False

        # Runtime vars provided from CLI (highest priority)
        if runtime_vars:
            if not isinstance(runtime_vars, Mapping):
                raise RenderError("runtime_vars must be a mapping")
            rv = dict(runtime_vars)
            vars_ctx = deep_merge(vars_ctx, rv)
            flat_rv = flatten_dict(rv)

            # Use explicit source map when provided (CLI/instances/etc.)
            for k in flat_rv.keys():
                if runtime_var_sources and k in runtime_var_sources:
                    vars_sources[k] = str(runtime_var_sources[k])
                else:
                    vars_sources[k] = "cli"

        if not name:
            inferred = infer_name_from_filename(requested_path)
            if inferred:
                name = inferred
                name_inferred_from_filename = True

        if not name:
            raise RenderError(f"Rendered connector has empty 'name' for {env_file}")
        guard_against_cyclic_name_reference(name, env_file=env_file)

        target_meta: Dict[str, Any] = {}
        if self.settings is not None:
            routing_meta: Dict[str, Any] = dict(connectctl_meta)
            if tags:
                routing_meta["tags"] = dedup_tags(tags)
            router = ClusterRouter(
                settings=self.settings,
                env=info.env,
                cli_cluster=(
                    routing_cli_cluster
                    if routing_cli_cluster is not None
                    else self.routing_cli_cluster
                ),
                suppress_tag_conflicts=(
                    routing_suppress_tag_conflicts
                    if routing_suppress_tag_conflicts is not None
                    else self.routing_suppress_tag_conflicts
                ),
            )
            decision = router.route(
                connector_name=name,
                connectctl_meta=routing_meta,
                connectctl_sources=merge.connectctl_sources,
            )
            target_meta = build_target_context(decision.cluster)

        ctx_flat, meta_flat, vars_sources = build_flat_placeholder_context(
            info,
            name=name,
            vars_ctx=vars_ctx,
            vars_sources=vars_sources,
            extra_meta=target_meta,
        )
        provider_base_context = dict(ctx_flat)
        provider_base_sources = dict(vars_sources)
        provider_context = VarProviderContext.from_flat_context(
            provider_base_context,
            sources=provider_base_sources,
            repo_root=self.repo.cfg.root,
            manifest_path=env_file,
            metadata=meta_flat,
        )
        provider_runtime = (
            VarProviderRuntime.from_settings(self.settings)
            if self.settings is not None
            else VarProviderRuntime.empty()
        )
        for provider_result in provider_runtime.evaluate_all(
            ctx_flat,
            provider_context=provider_context,
        ):
            for provider_value in provider_result.values:
                ctx_flat[provider_value.key] = provider_value.value
                vars_sources[provider_value.key] = provider_value.source

        computed_context = ComputedVarContext.from_flat_context(
            ctx_flat,
            sources=vars_sources,
            repo_root=self.repo.cfg.root,
            manifest_path=env_file,
            metadata=meta_flat,
        )
        computed_runtime = (
            ComputedVarRuntime.from_settings(self.settings)
            if self.settings is not None
            else ComputedVarRuntime.empty()
        )
        for computed in computed_runtime.evaluate_all(
            ctx_flat,
            computed_context=computed_context,
        ):
            ctx_flat[computed.name] = computed.value
            vars_sources[computed.name] = computed.source

        function_context = FunctionContext.from_flat_context(
            ctx_flat,
            sources=vars_sources,
            repo_root=self.repo.cfg.root,
            manifest_path=env_file,
            metadata=meta_flat,
        )

        resolved_name, resolved_config, trace = resolve_rendered_name_and_config(
            name,
            config,
            ctx_flat,
            env_file=env_file,
            template_runtime=self.template_runtime,
            function_context=function_context,
        )

        vars_used = build_vars_used(
            trace, ctx_flat=ctx_flat, meta_flat=meta_flat, vars_sources=vars_sources
        )

        manifest = ConnectorManifest(
            name=str(resolved_name),
            config=dict(resolved_config),
            source_path=env_file.resolve(),
            info=info,
            lifecycle=lifecycle,
        )

        meta_out: Dict[str, Any] = dict(connectctl_meta)
        if tags:
            meta_out["tags"] = dedup_tags(tags)

        return RenderResult(
            manifest=manifest,
            layers=tuple(layer_paths),
            connectctl=meta_out,
            connectctl_sources=merge.connectctl_sources,
            tags_sources=tuple(merge.tags_sources),
            name_first_set_by=name_first_set_by,
            name_last_set_by=name_last_set_by,
            name_inferred_from_filename=name_inferred_from_filename,
            vars_used=vars_used,
            placeholder_context=dict(ctx_flat),
            placeholder_sources=dict(vars_sources),
            provider_base_context=provider_base_context,
            provider_base_sources=provider_base_sources,
            provider_metadata=dict(meta_flat),
            template_config=dict(config),
            config_sources=config_sources,
            config_sources_chain=config_sources_chain,
            unset_config_keys=merge.unset_config_keys,
            unset_config_key_sources=merge.unset_config_key_sources,
        )

    def render_many(
        self,
        env_files: Sequence[Path],
        *,
        runtime_vars: Optional[Mapping[str, Any]] = None,
        runtime_var_sources: Optional[Mapping[str, Any]] = None,
        reuse_overrides: bool = True,
        reuse_from: Optional[Sequence[Path]] = None,
        routing_cli_cluster: Optional[str] = None,
        routing_suppress_tag_conflicts: Optional[bool] = None,
    ) -> List[RenderResult]:
        out: List[RenderResult] = []
        for p in env_files:
            out.append(
                self.render(
                    p,
                    runtime_vars=runtime_vars,
                    runtime_var_sources=runtime_var_sources,
                    reuse_overrides=reuse_overrides,
                    reuse_from=reuse_from,
                    routing_cli_cluster=routing_cli_cluster,
                    routing_suppress_tag_conflicts=routing_suppress_tag_conflicts,
                )
            )
        return out
