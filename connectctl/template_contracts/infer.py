from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from ..rendering.renderer_models import RenderResult
from ..template_graph import TemplateGraph


class TemplateContractInferer:
    """Builds deterministic starter contracts from one rendered manifest."""

    def __init__(self, *, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()

    def infer(
        self,
        *,
        manifest_path: Path,
        render_result: RenderResult,
        graph: TemplateGraph,
    ) -> dict[str, Any]:
        rel_manifest = _relative(self.repo_root, manifest_path)
        usages = _variable_usages(graph)
        inputs: dict[str, Any] = {}
        for name in sorted(usages):
            value = render_result.placeholder_context.get(name)
            inputs[name] = {
                "type": _infer_type(value),
                "required": False,
                "usages": list(usages[name]),
            }
        return {
            "version": 1,
            "contracts": [
                {
                    "name": f"{render_result.manifest.name} contract",
                    "manifests": [rel_manifest],
                    "inputs": inputs,
                }
            ],
        }


def _variable_usages(graph: TemplateGraph) -> dict[str, tuple[str, ...]]:
    direct: dict[str, set[str]] = defaultdict(set)
    function_targets: dict[str, set[str]] = defaultdict(set)
    function_args: dict[str, set[str]] = defaultdict(set)
    for edge in graph.edges:
        if edge.from_id.startswith("fn:") and edge.to_id.startswith("config:"):
            function_targets[edge.from_id.removeprefix("fn:")].add(
                edge.to_id.removeprefix("config:")
            )
        elif edge.from_id.startswith("var:") and edge.to_id.startswith("config:"):
            direct[edge.from_id.removeprefix("var:")].add(
                edge.to_id.removeprefix("config:")
            )
        elif edge.from_id.startswith("var:") and edge.to_id.startswith("fn:"):
            function_args[edge.from_id.removeprefix("var:")].add(
                edge.to_id.removeprefix("fn:")
            )
    for var_name, fn_names in function_args.items():
        for fn_name in fn_names:
            direct[var_name].update(function_targets.get(fn_name, ()))
    return {key: tuple(sorted(value)) for key, value in sorted(direct.items())}


def _infer_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    return "any"


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)
