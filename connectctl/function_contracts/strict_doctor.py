from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


RISKY_IMPORTS = {
    "boto3",
    "botocore",
    "httpx",
    "random",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}

RISKY_CALLS = {
    "compile",
    "eval",
    "exec",
    "open",
    "__import__",
}


@dataclass(frozen=True)
class StrictFunctionIssue:
    code: str
    file: Path
    line: int
    symbol: str
    message: str
    required_capability: str | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "code": self.code,
            "file": str(self.file),
            "line": self.line,
            "symbol": self.symbol,
            "message": self.message,
            "required_capability": self.required_capability,
        }


class StrictFunctionDoctor:
    """AST-based deterministic-safety diagnostics for repo-local functions."""

    def __init__(self, *, repo_root: Path, paths: Sequence[str]) -> None:
        self.repo_root = repo_root.resolve()
        self.paths = tuple(paths)

    def scan(self) -> tuple[StrictFunctionIssue, ...]:
        issues: list[StrictFunctionIssue] = []
        for path in self._iter_function_files():
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as e:
                issues.append(
                    StrictFunctionIssue(
                        code="syntax_error",
                        file=path,
                        line=e.lineno or 0,
                        symbol="syntax",
                        message=str(e),
                    )
                )
                continue
            issues.extend(_scan_tree(path, tree))
        return tuple(issues)

    def _iter_function_files(self) -> Iterable[Path]:
        for raw in self.paths:
            root = (self.repo_root / raw).resolve()
            try:
                root.relative_to(self.repo_root)
            except ValueError:
                continue
            if root.is_file() and root.suffix == ".py":
                yield root
            elif root.is_dir():
                for path in sorted(root.rglob("*.py")):
                    if path.name.startswith("_") or "__pycache__" in path.parts:
                        continue
                    yield path


def _scan_tree(path: Path, tree: ast.AST) -> list[StrictFunctionIssue]:
    issues: list[StrictFunctionIssue] = []
    capabilities = _declared_capabilities(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and _is_bkkt_function(node):
            issues.extend(_scan_function_signature(path, node))
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                required = _required_capability(root)
                if root in RISKY_IMPORTS and required not in capabilities:
                    issues.append(
                        _issue(
                            "risky_import",
                            path,
                            node.lineno,
                            alias.name,
                            required_capability=required,
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            required = _required_capability(root)
            if root in RISKY_IMPORTS and required not in capabilities:
                issues.append(
                    _issue(
                        "risky_import",
                        path,
                        node.lineno,
                        node.module or "",
                        required_capability=required,
                    )
                )
        elif isinstance(node, ast.Call):
            symbol = _call_symbol(node.func)
            root = symbol.split(".", 1)[0]
            required = _required_capability(symbol) or _required_capability(root)
            if (
                symbol in RISKY_CALLS
                or root in RISKY_IMPORTS
                or symbol in RISKY_IMPORTS
            ) and required not in capabilities:
                issues.append(
                    _issue(
                        "risky_call",
                        path,
                        node.lineno,
                        symbol,
                        required_capability=required,
                    )
                )
    return issues


def _declared_capabilities(tree: ast.AST) -> set[str]:
    capabilities: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and _is_bkkt_function(node):
            capabilities.update(_decorator_capabilities(node))
    return capabilities


def _decorator_capabilities(node: ast.FunctionDef) -> set[str]:
    capabilities: set[str] = set()
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        if _decorator_symbol(decorator) != "bkkt_function":
            continue
        for keyword in decorator.keywords:
            if keyword.arg != "capabilities":
                continue
            capabilities.update(_string_literals(keyword.value))
    return capabilities


def _string_literals(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        values: set[str] = set()
        for item in node.elts:
            values.update(_string_literals(item))
        return values
    return set()


def _scan_function_signature(
    path: Path, node: ast.FunctionDef
) -> list[StrictFunctionIssue]:
    issues: list[StrictFunctionIssue] = []
    for arg in (*node.args.args, *node.args.kwonlyargs):
        symbol = f"{node.name}.{arg.arg}"
        if arg.annotation is None:
            issues.append(
                _signature_issue(
                    "signature_missing_parameter_annotation",
                    path,
                    arg.lineno,
                    symbol,
                    (
                        f"Parameter {arg.arg!r} in repo-local function {node.name!r} "
                        "must have an explicit type annotation."
                    ),
                )
            )
        if arg.arg == "ctx" and not _is_function_context_annotation(arg.annotation):
            issues.append(
                _signature_issue(
                    "signature_ctx_untyped",
                    path,
                    arg.lineno,
                    symbol,
                    (
                        "Context parameter `ctx` must be annotated as "
                        "`FunctionContext` so authoring tools and contract tests "
                        "can explain the function API."
                    ),
                )
            )
    if node.returns is None:
        issues.append(
            _signature_issue(
                "signature_missing_return_annotation",
                path,
                node.lineno,
                node.name,
                (
                    f"Repo-local function {node.name!r} must declare a scalar "
                    "return annotation: str, int, float or bool."
                ),
            )
        )
    elif not _is_scalar_return_annotation(node.returns):
        issues.append(
            _signature_issue(
                "signature_non_scalar_return_annotation",
                path,
                node.lineno,
                node.name,
                (
                    f"Repo-local function {node.name!r} must return a scalar "
                    "str/int/float/bool value."
                ),
            )
        )
    return issues


def _is_bkkt_function(node: ast.FunctionDef) -> bool:
    return any(
        _decorator_symbol(decorator) == "bkkt_function"
        for decorator in node.decorator_list
    )


def _decorator_symbol(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _decorator_symbol(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _is_function_context_annotation(node: ast.AST | None) -> bool:
    if node is None:
        return False
    return _annotation_name(node).endswith("FunctionContext")


def _is_scalar_return_annotation(node: ast.AST) -> bool:
    names = _annotation_names(node)
    return bool(names) and names <= {"str", "int", "float", "bool"}


def _annotation_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _annotation_names(node.left) | _annotation_names(node.right)
    if isinstance(node, ast.Subscript) and _annotation_name(node.value) == "Union":
        slice_node = node.slice
        if isinstance(slice_node, ast.Tuple):
            return {name for elt in slice_node.elts for name in _annotation_names(elt)}
        return _annotation_names(slice_node)
    name = _annotation_name(node)
    return {name.rsplit(".", 1)[-1]} if name else set()


def _annotation_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Attribute):
        base = _annotation_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        return _annotation_name(node.value)
    return ""


def _call_symbol(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_symbol(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return type(node).__name__


def _required_capability(symbol: str) -> str | None:
    root = symbol.split(".", 1)[0]
    if root in {"requests", "httpx", "urllib", "socket"}:
        return "network"
    if root in {"boto3", "botocore"}:
        return "aws"
    if root == "random":
        return "random"
    if root == "subprocess":
        return "process"
    if symbol == "open":
        return "filesystem"
    if symbol in {"compile", "eval", "exec", "__import__"}:
        return "dynamic_code"
    return None


def _issue(
    code: str,
    path: Path,
    line: int,
    symbol: str,
    *,
    required_capability: str | None,
) -> StrictFunctionIssue:
    capability_hint = (
        f" If this is intentional, declare capabilities=({required_capability!r},)."
        if required_capability
        else ""
    )
    return StrictFunctionIssue(
        code=code,
        file=path,
        line=line,
        symbol=symbol,
        message=(
            f"{symbol!r} makes repo-local functions non-deterministic or side-effectful. "
            "Keep BKKT render functions pure and fast; move external IO to CI/preflight."
            + capability_hint
        ),
        required_capability=required_capability,
    )


def _signature_issue(
    code: str, path: Path, line: int, symbol: str, message: str
) -> StrictFunctionIssue:
    return StrictFunctionIssue(
        code=code,
        file=path,
        line=line,
        symbol=symbol,
        message=message,
    )
