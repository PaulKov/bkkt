from __future__ import annotations

from pathlib import Path

from ..exceptions import ConnectCtlError
from ..rendering.renderer_models import RenderResult
from ..template_graph import TemplateGraph
from ..utils import flatten_dict
from .models import ConfigTraceReport, TraceStep, VarTraceReport, VarTraceUsage


class TemplateTracer:
    """Builds user-facing traces from render results and raw template graphs."""

    def __init__(self, *, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()

    def trace_config_key(
        self,
        render_result: RenderResult,
        graph: TemplateGraph,
        *,
        config_key: str,
    ) -> ConfigTraceReport:
        flat_config = flatten_dict(render_result.manifest.config)
        if config_key not in flat_config:
            raise ConnectCtlError(
                f"Config key {config_key!r} not found in rendered manifest "
                f"{render_result.manifest.source_path}"
            )
        steps: list[TraceStep] = []
        source = render_result.config_sources.get(config_key)
        chain = tuple(render_result.config_sources_chain.get(config_key) or ())
        steps.append(
            TraceStep(
                kind="config_source",
                name=config_key,
                value=flat_config[config_key],
                source=source,
                detail=" -> ".join(chain) if chain else None,
            )
        )
        for variable in self._variables_for_config(graph, config_key):
            steps.append(
                TraceStep(
                    kind="variable",
                    name=variable,
                    value=render_result.placeholder_context.get(variable),
                    source=render_result.placeholder_sources.get(variable),
                )
            )
            steps.extend(
                self._source_steps_for_variable(render_result, graph, variable)
            )
        for function in self._functions_for_config(graph, config_key):
            steps.append(TraceStep(kind="function", name=function))
        return ConfigTraceReport(
            manifest=_relative(render_result.manifest.source_path, self.repo_root),
            config_key=config_key,
            final_value=flat_config[config_key],
            steps=tuple(steps),
        )

    def trace_var(
        self,
        render_result: RenderResult,
        graph: TemplateGraph,
        *,
        variable: str,
    ) -> VarTraceReport:
        usages = tuple(
            sorted(
                self._variable_usages(graph, variable),
                key=lambda item: (item.config_key, item.kind, item.via_function or ""),
            )
        )
        steps = (
            TraceStep(
                kind="variable",
                name=variable,
                value=render_result.placeholder_context.get(variable),
                source=render_result.placeholder_sources.get(variable),
            ),
            *self._source_steps_for_variable(render_result, graph, variable),
        )
        return VarTraceReport(
            manifest=_relative(render_result.manifest.source_path, self.repo_root),
            variable=variable,
            value=render_result.placeholder_context.get(variable),
            source=render_result.placeholder_sources.get(variable),
            usages=usages,
            steps=steps,
        )

    def _variables_for_config(
        self, graph: TemplateGraph, config_key: str
    ) -> tuple[str, ...]:
        config_node = f"config:{config_key}"
        direct = {
            edge.from_id.removeprefix("var:")
            for edge in graph.edges
            if edge.to_id == config_node and edge.from_id.startswith("var:")
        }
        function_nodes = {
            edge.from_id
            for edge in graph.edges
            if edge.to_id == config_node and edge.from_id.startswith("fn:")
        }
        via_function = {
            edge.from_id.removeprefix("var:")
            for edge in graph.edges
            if edge.to_id in function_nodes and edge.from_id.startswith("var:")
        }
        return tuple(sorted(direct | via_function))

    def _functions_for_config(
        self, graph: TemplateGraph, config_key: str
    ) -> tuple[str, ...]:
        config_node = f"config:{config_key}"
        return tuple(
            sorted(
                edge.from_id.removeprefix("fn:")
                for edge in graph.edges
                if edge.to_id == config_node and edge.from_id.startswith("fn:")
            )
        )

    def _variable_usages(
        self, graph: TemplateGraph, variable: str
    ) -> tuple[VarTraceUsage, ...]:
        var_node = f"var:{variable}"
        function_targets = _function_config_targets(graph)
        usages: set[VarTraceUsage] = set()
        for edge in graph.edges:
            if edge.from_id != var_node:
                continue
            if edge.to_id.startswith("config:"):
                usages.add(
                    VarTraceUsage(
                        config_key=edge.to_id.removeprefix("config:"),
                        kind=edge.kind,
                    )
                )
            elif edge.to_id.startswith("fn:"):
                fn_name = edge.to_id.removeprefix("fn:")
                for config_key in function_targets.get(fn_name, ()):
                    usages.add(
                        VarTraceUsage(
                            config_key=config_key,
                            kind=edge.kind,
                            via_function=fn_name,
                        )
                    )
        return tuple(usages)

    def _source_steps_for_variable(
        self,
        render_result: RenderResult,
        graph: TemplateGraph,
        variable: str,
    ) -> tuple[TraceStep, ...]:
        steps: list[TraceStep] = []
        seen: set[tuple[str, str]] = set()

        def add(step: TraceStep) -> None:
            key = (step.kind, step.name)
            if key in seen:
                return
            seen.add(key)
            steps.append(step)

        def visit_var(name: str) -> None:
            var_id = f"var:{name}"
            for edge in graph.edges:
                if edge.to_id != var_id or edge.kind != "provides":
                    continue
                if edge.from_id.startswith("provider:"):
                    provider = edge.from_id.removeprefix("provider:")
                    add(
                        TraceStep(
                            kind="provider",
                            name=provider,
                            source=f"provider:{provider}",
                        )
                    )
                elif edge.from_id.startswith("computed:"):
                    computed = edge.from_id.removeprefix("computed:")
                    add(
                        TraceStep(
                            kind="computed",
                            name=computed,
                            value=render_result.placeholder_context.get(name),
                            source=f"computed:{computed}",
                        )
                    )
                    visit_computed(computed)

        def visit_computed(name: str) -> None:
            computed_id = f"computed:{name}"
            for edge in graph.edges:
                if edge.to_id != computed_id or edge.kind != "depends_on":
                    continue
                add(
                    TraceStep(
                        kind="graph_edge",
                        name=f"{edge.from_id} -> {edge.to_id}",
                        detail=edge.kind,
                    )
                )
                if edge.from_id.startswith("var:"):
                    dependency = edge.from_id.removeprefix("var:")
                    add(
                        TraceStep(
                            kind="variable",
                            name=dependency,
                            value=render_result.placeholder_context.get(dependency),
                            source=render_result.placeholder_sources.get(dependency),
                        )
                    )
                    visit_var(dependency)
                elif edge.from_id.startswith("computed:"):
                    dependency = edge.from_id.removeprefix("computed:")
                    add(
                        TraceStep(
                            kind="computed",
                            name=dependency,
                            source=f"computed:{dependency}",
                        )
                    )
                    visit_computed(dependency)

        visit_var(variable)
        return tuple(steps)


def _function_config_targets(graph: TemplateGraph) -> dict[str, tuple[str, ...]]:
    targets: dict[str, set[str]] = {}
    for edge in graph.edges:
        if edge.from_id.startswith("fn:") and edge.to_id.startswith("config:"):
            targets.setdefault(edge.from_id.removeprefix("fn:"), set()).add(
                edge.to_id.removeprefix("config:")
            )
    return {key: tuple(sorted(value)) for key, value in targets.items()}


def _relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)
