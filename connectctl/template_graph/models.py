from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


NodeKind = Literal["config", "function", "variable", "provider", "computed"]
EdgeKind = Literal["placeholder", "fn_arg", "renders", "provides", "depends_on"]


@dataclass(frozen=True, order=True)
class TemplateGraphNode:
    id: str
    kind: NodeKind
    label: str

    def to_payload(self) -> dict[str, str]:
        return {"id": self.id, "kind": self.kind, "label": self.label}


@dataclass(frozen=True, order=True)
class TemplateGraphEdge:
    from_id: str
    to_id: str
    kind: EdgeKind

    def to_payload(self) -> dict[str, str]:
        return {"from": self.from_id, "to": self.to_id, "kind": self.kind}


@dataclass(frozen=True)
class TemplateGraph:
    nodes: tuple[TemplateGraphNode, ...]
    edges: tuple[TemplateGraphEdge, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "nodes": [node.to_payload() for node in self.nodes],
            "edges": [edge.to_payload() for edge in self.edges],
        }
