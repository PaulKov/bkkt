from __future__ import annotations

import ast
from typing import Any, Iterable, Mapping

from ..utils import flatten_dict
from .models import TemplateGraph, TemplateGraphEdge, TemplateGraphNode


class TemplateGraphExtractor:
    """Extracts placeholder variable/function dependencies from raw config."""

    def extract_from_config(self, config: Mapping[str, Any]) -> TemplateGraph:
        nodes: set[TemplateGraphNode] = set()
        edges: set[TemplateGraphEdge] = set()
        for key, value in flatten_dict(config).items():
            config_node = TemplateGraphNode(
                id=f"config:{key}", kind="config", label=key
            )
            for text in _iter_strings(value):
                refs = _extract_refs(text)
                if not refs:
                    continue
                nodes.add(config_node)
                for ref in refs:
                    if ref.kind == "variable":
                        var_node = TemplateGraphNode(
                            id=f"var:{ref.name}", kind="variable", label=ref.name
                        )
                        nodes.add(var_node)
                        edges.add(
                            TemplateGraphEdge(
                                from_id=var_node.id,
                                to_id=config_node.id,
                                kind="placeholder",
                            )
                        )
                    else:
                        fn_node = TemplateGraphNode(
                            id=f"fn:{ref.name}", kind="function", label=ref.name
                        )
                        nodes.add(fn_node)
                        edges.add(
                            TemplateGraphEdge(
                                from_id=fn_node.id,
                                to_id=config_node.id,
                                kind="renders",
                            )
                        )
                        for arg in ref.args:
                            var_node = TemplateGraphNode(
                                id=f"var:{arg}", kind="variable", label=arg
                            )
                            nodes.add(var_node)
                            edges.add(
                                TemplateGraphEdge(
                                    from_id=var_node.id,
                                    to_id=fn_node.id,
                                    kind="fn_arg",
                                )
                            )
        return TemplateGraph(nodes=tuple(sorted(nodes)), edges=tuple(sorted(edges)))


class _Ref:
    def __init__(self, *, kind: str, name: str, args: tuple[str, ...] = ()) -> None:
        self.kind = kind
        self.name = name
        self.args = args


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for nested in value.values():
            yield from _iter_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_strings(nested)


def _extract_refs(text: str) -> list[_Ref]:
    refs: list[_Ref] = []
    for inner in _placeholder_inners(text):
        if inner.startswith("fn:"):
            refs.append(_function_ref(inner))
        elif ":" in inner:
            # Kafka Connect ConfigProvider placeholder. It may still contain nested
            # BKKT placeholders, e.g. ${secretManager:${db.secret}:host}.
            refs.extend(_extract_refs(inner))
        else:
            refs.append(_Ref(kind="variable", name=inner.strip()))
    return refs


def _placeholder_inners(text: str) -> list[str]:
    inners: list[str] = []
    i = 0
    while i < len(text):
        start = text.find("${", i)
        if start < 0:
            break
        depth = 1
        j = start + 2
        while j < len(text):
            if text.startswith("${", j):
                depth += 1
                j += 2
                continue
            if text[j] == "}":
                depth -= 1
                if depth == 0:
                    inners.append(text[start + 2 : j])
                    i = j + 1
                    break
            j += 1
        else:
            break
    return inners


def _function_ref(inner: str) -> _Ref:
    expr = inner.split(":", 1)[1].strip()
    try:
        parsed = ast.parse(expr, mode="eval")
    except SyntaxError:
        return _Ref(kind="function", name=expr, args=())
    if not isinstance(parsed.body, ast.Call):
        return _Ref(kind="function", name=expr, args=())
    fn_name = _call_name(parsed.body.func)
    if not fn_name:
        return _Ref(kind="function", name=expr, args=())
    args = tuple(
        _arg_name(arg)
        for arg in [*parsed.body.args, *(kw.value for kw in parsed.body.keywords)]
    )
    return _Ref(
        kind="function",
        name=fn_name,
        args=tuple(arg for arg in args if arg),
    )


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts: list[str] = []
        cur: ast.AST = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            return ".".join(reversed(parts))
    return None


def _arg_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts: list[str] = []
        cur: ast.AST = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            return ".".join(reversed(parts))
    return None
