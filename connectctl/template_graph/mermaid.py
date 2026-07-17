from __future__ import annotations

import re

from .models import TemplateGraph


def render_mermaid(graph: TemplateGraph) -> str:
    lines = ["graph TD"]
    for node in graph.nodes:
        lines.append(f'  {_node_id(node.id)}["{_escape(node.label)}"]')
    for edge in graph.edges:
        lines.append(
            f"  {_node_id(edge.from_id)} -->|{edge.kind}| {_node_id(edge.to_id)}"
        )
    return "\n".join(lines) + "\n"


def _node_id(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]", "_", value)


def _escape(value: str) -> str:
    return value.replace('"', '\\"')
