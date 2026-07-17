from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Mapping

from ..exceptions import ConnectCtlError
from .models import (
    ComputedVarDescriptor,
    ComputedVarGraph,
    ComputedVarGraphEdge,
    ComputedVarGraphNode,
)
from .registry import ComputedVarRegistry


class ComputedVarDependencyGraph:
    """Dependency graph for repo-local computed variables."""

    def __init__(self, registry: ComputedVarRegistry) -> None:
        self.registry = registry
        self._by_name = {item.name: item for item in registry.list()}

    def evaluation_order(
        self,
        *,
        context: Mapping[str, Any],
        target: str | None = None,
    ) -> tuple[ComputedVarDescriptor, ...]:
        targets = (target,) if target else tuple(sorted(self._by_name))
        order: list[ComputedVarDescriptor] = []
        state: dict[str, str] = {}
        stack: list[str] = []

        for name in targets:
            self._visit(name, context=context, state=state, stack=stack, order=order)
        return tuple(order)

    def impact(self, name: str) -> tuple[str, ...]:
        dependents = self._dependents()
        seen: set[str] = set()
        ordered: list[str] = []

        def visit(current: str) -> None:
            for dependent in sorted(dependents.get(current, ())):
                if dependent in seen:
                    continue
                seen.add(dependent)
                ordered.append(dependent)
                visit(dependent)

        visit(name)
        return tuple(ordered)

    def to_graph(self) -> ComputedVarGraph:
        nodes: set[ComputedVarGraphNode] = set()
        edges: set[ComputedVarGraphEdge] = set()
        computed_names = set(self._by_name)
        for descriptor in self._by_name.values():
            current = _computed_node(descriptor.name)
            nodes.add(current)
            for dependency in descriptor.dependencies:
                dependency_node = (
                    _computed_node(dependency)
                    if dependency in computed_names
                    else _variable_node(dependency)
                )
                nodes.add(dependency_node)
                edges.add(
                    ComputedVarGraphEdge(
                        from_id=dependency_node.id,
                        to_id=current.id,
                        kind="depends_on",
                    )
                )
        return ComputedVarGraph(nodes=tuple(sorted(nodes)), edges=tuple(sorted(edges)))

    def _visit(
        self,
        name: str,
        *,
        context: Mapping[str, Any],
        state: dict[str, str],
        stack: list[str],
        order: list[ComputedVarDescriptor],
    ) -> None:
        if name not in self._by_name:
            if name in context:
                return
            current = stack[-1] if stack else name
            raise ConnectCtlError(
                f"Computed variable {current!r} has missing dependency {name!r}. "
                "Add the variable to repo vars/render vars or register a computed var "
                "with that name."
            )
        current_state = state.get(name)
        if current_state == "done":
            return
        if current_state == "visiting":
            cycle_start = stack.index(name) if name in stack else 0
            cycle = [*stack[cycle_start:], name]
            raise ConnectCtlError(
                "Computed variable dependency cycle detected: "
                + " -> ".join(cycle)
                + ". Break the cycle or remove one depends_on edge."
            )

        state[name] = "visiting"
        stack.append(name)
        descriptor = self._by_name[name]
        for dependency in descriptor.dependencies:
            self._visit(
                dependency,
                context=context,
                state=state,
                stack=stack,
                order=order,
            )
        stack.pop()
        state[name] = "done"
        order.append(descriptor)

    def _dependents(self) -> dict[str, tuple[str, ...]]:
        dependents: dict[str, set[str]] = defaultdict(set)
        for descriptor in self._by_name.values():
            for dependency in descriptor.dependencies:
                dependents[dependency].add(descriptor.name)
        return {key: tuple(sorted(value)) for key, value in dependents.items()}


def render_mermaid(graph: ComputedVarGraph) -> str:
    lines = ["graph TD"]
    for node in graph.nodes:
        lines.append(f'  {_node_id(node.id)}["{_escape(node.label)}"]')
    for edge in graph.edges:
        lines.append(
            f"  {_node_id(edge.from_id)} -->|{edge.kind}| {_node_id(edge.to_id)}"
        )
    return "\n".join(lines) + "\n"


def _computed_node(name: str) -> ComputedVarGraphNode:
    return ComputedVarGraphNode(
        id=f"computed:{name}",
        kind="computed",
        label=name,
    )


def _variable_node(name: str) -> ComputedVarGraphNode:
    return ComputedVarGraphNode(
        id=f"var:{name}",
        kind="variable",
        label=name,
    )


def _node_id(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]", "_", value)


def _escape(value: str) -> str:
    return value.replace('"', '\\"')
