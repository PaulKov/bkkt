from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from ...app.context import CliContext
from ..connector_facts import ConnectorFacts
from .discovery import DiscoveryOptions, DiscoveryService, related_facts
from .formatting import emit_extended_output, join_csv


@dataclass(frozen=True)
class GraphNode:
    id: str
    label: str
    kind: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label, "kind": self.kind}


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    label: str

    def to_dict(self) -> dict[str, str]:
        return {"source": self.source, "target": self.target, "label": self.label}


class LineageService:
    """Build a best-effort data lineage graph from connector facts."""

    def __init__(self, *, ctx: CliContext, logger: Optional[logging.Logger] = None):
        self.ctx = ctx
        self.log = logger or ctx.logger

    def run(self, args: Any) -> int:
        options = DiscoveryOptions.from_args(args, default_limit=100)
        discovery = DiscoveryService(ctx=self.ctx, logger=self.log).resolve(
            str(getattr(args, "object")), options=options, args=args
        )
        facts = related_facts(discovery.results, discovery.facts)
        nodes, edges = build_lineage_graph(facts)
        payload = {
            "object": discovery.query_object,
            "source": options.source.value,
            "env": list(options.envs),
            "cluster": options.cluster_filter or "all",
            "matched_connectors": [item.facts.name for item in discovery.results],
            "nodes": [node.to_dict() for node in nodes],
            "edges": [edge.to_dict() for edge in edges],
            "warnings": list(discovery.warnings),
        }
        text = render_lineage_text(payload)
        mermaid = render_mermaid(nodes, edges)
        emit_extended_output(
            payload,
            output=str(getattr(args, "output", "text")),
            text=text,
            markdown=text + "\n```mermaid\n" + mermaid + "```\n",
            mermaid=mermaid,
        )
        return 0


def build_lineage_graph(
    facts_list: tuple[ConnectorFacts, ...],
) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    nodes: dict[str, GraphNode] = {}
    edges: dict[tuple[str, str, str], GraphEdge] = {}

    def node(kind: str, label: str) -> str:
        node_id = f"{kind}:{label}"
        nodes.setdefault(node_id, GraphNode(id=node_id, label=label, kind=kind))
        return node_id

    def edge(src: str, dst: str, label: str) -> None:
        edges.setdefault(
            (src, dst, label), GraphEdge(source=src, target=dst, label=label)
        )

    for facts in facts_list:
        connector = node("connector", facts.name)
        if facts.connector_type == "source":
            for table in facts.source_tables:
                edge(node("table", table), connector, "captures")
            produced = facts.produced_topics or (
                (facts.produced_pattern,) if facts.produced_pattern else ()
            )
            for topic in produced:
                edge(connector, node("topic", topic), "produces")
        elif facts.connector_type == "sink":
            consumed = facts.consumed_topics or facts.topic_patterns()
            for topic in consumed:
                edge(node("topic", topic), connector, "consumes")
            sink_tables = facts.sink_table_full_names() or facts.sink_tables
            for table in sink_tables:
                edge(connector, node("table", table), "writes")
        else:
            for topic in facts.consumed_topics:
                edge(node("topic", topic), connector, "uses")
            for topic in facts.produced_topics:
                edge(connector, node("topic", topic), "produces")
    return tuple(sorted(nodes.values(), key=lambda n: (n.kind, n.label))), tuple(
        edges.values()
    )


def render_lineage_text(payload: dict[str, Any]) -> str:
    lines = [
        f"BKKT lineage: object={payload['object']} source={payload['source']} env={join_csv(payload['env'])} cluster={payload['cluster']}\n",
        f"Matched connectors: {join_csv(payload['matched_connectors'])}\n\n",
        "Edges:\n",
    ]
    if not payload["edges"]:
        lines.append("- no lineage edges found\n")
    for edge in payload["edges"]:
        lines.append(f"- {edge['source']} --{edge['label']}--> {edge['target']}\n")
    if payload.get("warnings"):
        lines.append("\nWarnings:\n")
        for warning in payload["warnings"]:
            lines.append(f"- {warning}\n")
    return "".join(lines)


def render_mermaid(nodes: tuple[GraphNode, ...], edges: tuple[GraphEdge, ...]) -> str:
    lines = ["flowchart LR\n"]
    for node in nodes:
        lines.append(f'  {mermaid_id(node.id)}["{_escape(node.label)}"]\n')
    for edge in edges:
        lines.append(
            f"  {mermaid_id(edge.source)} -->|{_escape(edge.label)}| {mermaid_id(edge.target)}\n"
        )
    return "".join(lines)


def mermaid_id(raw: str) -> str:
    return "n_" + re.sub(r"[^A-Za-z0-9_]", "_", raw)


def _escape(raw: str) -> str:
    return raw.replace('"', '\\"')


__all__ = [
    "GraphEdge",
    "GraphNode",
    "LineageService",
    "build_lineage_graph",
    "render_mermaid",
]
