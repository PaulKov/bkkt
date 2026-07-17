from __future__ import annotations

from ..computed_vars import ComputedVarRuntime
from ..rendering.renderer_models import RenderResult
from ..settings_models import Settings
from .extractor import TemplateGraphExtractor
from .models import TemplateGraph, TemplateGraphEdge, TemplateGraphNode


class TemplateExecutionGraphBuilder:
    """Builds an end-to-end graph for rendered template execution."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    def build(self, render_result: RenderResult) -> TemplateGraph:
        graph = TemplateGraphExtractor().extract_from_config(
            render_result.template_config
        )
        nodes = set(graph.nodes)
        edges = set(graph.edges)
        self._add_value_sources(render_result, nodes=nodes, edges=edges)
        self._add_computed_dependencies(nodes=nodes, edges=edges)
        return TemplateGraph(nodes=tuple(sorted(nodes)), edges=tuple(sorted(edges)))

    def _add_value_sources(
        self,
        render_result: RenderResult,
        *,
        nodes: set[TemplateGraphNode],
        edges: set[TemplateGraphEdge],
    ) -> None:
        for key, source in sorted(render_result.placeholder_sources.items()):
            variable = _variable_node(key)
            nodes.add(variable)
            if source.startswith("provider:"):
                provider_name = source.removeprefix("provider:")
                provider = _provider_node(provider_name)
                nodes.add(provider)
                edges.add(
                    TemplateGraphEdge(
                        from_id=provider.id,
                        to_id=variable.id,
                        kind="provides",
                    )
                )
            elif source.startswith("computed:"):
                computed_name = source.removeprefix("computed:")
                computed = _computed_node(computed_name)
                nodes.add(computed)
                edges.add(
                    TemplateGraphEdge(
                        from_id=computed.id,
                        to_id=variable.id,
                        kind="provides",
                    )
                )

    def _add_computed_dependencies(
        self,
        *,
        nodes: set[TemplateGraphNode],
        edges: set[TemplateGraphEdge],
    ) -> None:
        if self.settings is None:
            return
        computed_graph = ComputedVarRuntime.from_settings(self.settings).graph()
        for node in computed_graph.nodes:
            if node.kind == "computed":
                nodes.add(_computed_node(node.label))
            else:
                nodes.add(_variable_node(node.label))
        for edge in computed_graph.edges:
            edges.add(
                TemplateGraphEdge(
                    from_id=edge.from_id,
                    to_id=edge.to_id,
                    kind="depends_on",
                )
            )


def _provider_node(name: str) -> TemplateGraphNode:
    return TemplateGraphNode(id=f"provider:{name}", kind="provider", label=name)


def _computed_node(name: str) -> TemplateGraphNode:
    return TemplateGraphNode(id=f"computed:{name}", kind="computed", label=name)


def _variable_node(name: str) -> TemplateGraphNode:
    return TemplateGraphNode(id=f"var:{name}", kind="variable", label=name)
