from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal


ComputedVarSource = Literal["repo"]


@dataclass(frozen=True)
class ComputedVarDescriptor:
    name: str
    fn: Callable[..., Any]
    description: str
    source: ComputedVarSource
    source_path: Path | None = None
    allow_shadow: bool = False
    dependencies: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description.strip(),
            "source": self.source,
            "source_path": str(self.source_path) if self.source_path else None,
            "allow_shadow": self.allow_shadow,
            "dependencies": list(self.dependencies),
            "capabilities": list(self.capabilities),
        }


@dataclass(frozen=True)
class ComputedVarValue:
    name: str
    value: str | int | float | bool
    source: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "source": self.source,
        }


ComputedVarGraphNodeKind = Literal["computed", "variable"]
ComputedVarGraphEdgeKind = Literal["depends_on"]


@dataclass(frozen=True, order=True)
class ComputedVarGraphNode:
    id: str
    kind: ComputedVarGraphNodeKind
    label: str

    def to_payload(self) -> dict[str, str]:
        return {"id": self.id, "kind": self.kind, "label": self.label}


@dataclass(frozen=True, order=True)
class ComputedVarGraphEdge:
    from_id: str
    to_id: str
    kind: ComputedVarGraphEdgeKind

    def to_payload(self) -> dict[str, str]:
        return {"from": self.from_id, "to": self.to_id, "kind": self.kind}


@dataclass(frozen=True)
class ComputedVarGraph:
    nodes: tuple[ComputedVarGraphNode, ...]
    edges: tuple[ComputedVarGraphEdge, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "nodes": [node.to_payload() for node in self.nodes],
            "edges": [edge.to_payload() for edge in self.edges],
        }


@dataclass(frozen=True)
class ComputedVarContractCase:
    name: str
    variable: str
    expect: Any
    manifest: str | None = None
    source_path: Path | None = None


@dataclass(frozen=True)
class ComputedVarContractResult:
    case: ComputedVarContractCase
    status: Literal["passed", "failed"]
    actual: Any | None = None
    error: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.case.name,
            "variable": self.case.variable,
            "status": self.status,
            "expected": self.case.expect,
            "actual": self.actual,
            "error": self.error,
            "source_path": (
                str(self.case.source_path) if self.case.source_path else None
            ),
        }


@dataclass(frozen=True)
class ComputedVarContractSuite:
    results: tuple[ComputedVarContractResult, ...]

    @property
    def failed(self) -> int:
        return sum(1 for item in self.results if item.status == "failed")

    @property
    def passed(self) -> int:
        return sum(1 for item in self.results if item.status == "passed")

    @property
    def status(self) -> str:
        return "failed" if self.failed else "ok"

    @property
    def exit_code(self) -> int:
        return 1 if self.failed else 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": {
                "total": len(self.results),
                "passed": self.passed,
                "failed": self.failed,
            },
            "cases": [item.to_payload() for item in self.results],
        }
