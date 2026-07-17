from __future__ import annotations

import ast
import math
import statistics
from pathlib import Path
from typing import Dict, List, Sequence, Set

from .models import CouplingStats


def percentile(sorted_vals: Sequence[int], p: float) -> float:
    """Nearest-rank percentile for a sorted integer list."""

    if not sorted_vals:
        return 0.0
    if p <= 0:
        return float(sorted_vals[0])
    if p >= 100:
        return float(sorted_vals[-1])
    k = int(math.ceil((p / 100.0) * len(sorted_vals)))
    k = max(1, min(len(sorted_vals), k))
    return float(sorted_vals[k - 1])


def module_name_from_path(py_path: Path, *, connectctl_dir: Path) -> str:
    rel = py_path.relative_to(connectctl_dir)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    if not parts:
        return "connectctl"
    return "connectctl." + ".".join(parts)


def _module_package_parts(module_name: str, *, is_package: bool) -> List[str]:
    parts = module_name.split(".")
    return parts if is_package else parts[:-1]


def _resolve_import_from(
    *, src_module: str, src_is_package: bool, node: ast.ImportFrom
) -> List[str]:
    if node.module == "__future__":
        return []

    if node.level == 0:
        return [node.module] if node.module else []

    pkg_parts = _module_package_parts(src_module, is_package=src_is_package)
    up = node.level - 1
    if up > 0:
        pkg_parts = pkg_parts[: max(0, len(pkg_parts) - up)]

    if node.module:
        return [".".join(pkg_parts + node.module.split("."))]

    # from .. import foo, bar
    out: List[str] = []
    for a in node.names:
        if a.name == "*":
            continue
        out.append(".".join(pkg_parts + [a.name]))
    return out


def collect_internal_deps(
    connectctl_dir: Path,
    *,
    module_files: Sequence[Path],
) -> Dict[str, Set[str]]:
    """Граф import‑зависимостей: src_module -> {target_modules} только внутри connectctl.*"""

    module_to_path: Dict[str, Path] = {}
    is_package: Dict[str, bool] = {}
    for f in module_files:
        name = module_name_from_path(f, connectctl_dir=connectctl_dir)
        module_to_path[name] = f
        is_package[name] = f.name == "__init__.py"

    module_set = set(module_to_path)
    deps_out: Dict[str, Set[str]] = {m: set() for m in module_set}

    for src_module, f in module_to_path.items():
        try:
            src = f.read_text(encoding="utf-8")
        except Exception:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue

        candidates: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    candidates.append(a.name)
            elif isinstance(node, ast.ImportFrom):
                candidates.extend(
                    _resolve_import_from(
                        src_module=src_module,
                        src_is_package=is_package.get(src_module, False),
                        node=node,
                    )
                )

        for c in candidates:
            if not c.startswith("connectctl"):
                continue
            tgt = c
            while tgt not in module_set and "." in tgt:
                tgt = tgt.rsplit(".", 1)[0]
            if tgt in module_set and tgt != src_module:
                deps_out[src_module].add(tgt)

    return deps_out


def slice_group(module_name: str) -> str:
    """Группировка модулей в «слайсы».

    - connectctl.commands.<feature>...
    - connectctl.services.<feature>...
    - иначе connectctl.<top>
    """

    parts = module_name.split(".")
    if len(parts) == 1:
        return "connectctl.root"
    if parts[1] in {"commands", "services"} and len(parts) >= 3:
        return "connectctl." + parts[1] + "." + parts[2]
    return "connectctl." + parts[1]


def connected_components(
    nodes: Sequence[str], undirected_adj: Dict[str, Set[str]]
) -> List[Set[str]]:
    seen: Set[str] = set()
    comps: List[Set[str]] = []
    for n in nodes:
        if n in seen:
            continue
        stack = [n]
        comp: Set[str] = set()
        seen.add(n)
        while stack:
            x = stack.pop()
            comp.add(x)
            for y in undirected_adj.get(x, set()):
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        comps.append(comp)
    return comps


def avg_clustering(nodes: Sequence[str], undirected_adj: Dict[str, Set[str]]) -> float:
    """Average clustering coefficient for undirected graph."""

    total = 0.0
    for n in nodes:
        neigh = list(undirected_adj.get(n, set()))
        k = len(neigh)
        if k < 2:
            continue
        edges = 0
        neigh_set = set(neigh)
        for u in neigh:
            edges += len(undirected_adj.get(u, set()) & neigh_set)
        edges = edges // 2
        total += (2.0 * edges) / (k * (k - 1))
    return total / max(1, len(nodes))


def compute_coupling_stats(
    deps_out: Dict[str, Set[str]], *, top_n: int
) -> CouplingStats:
    modules = sorted(deps_out)
    n = len(modules)
    ce_list = [len(deps_out[m]) for m in modules]
    ce_sorted = sorted(ce_list)

    ca: Dict[str, int] = {m: 0 for m in modules}
    edges = 0
    for src, tgts in deps_out.items():
        for tgt in tgts:
            ca[tgt] = ca.get(tgt, 0) + 1
            edges += 1

    avg_ce = float(sum(ce_list) / n) if n else 0.0
    med_ce = float(statistics.median(ce_sorted)) if ce_sorted else 0.0
    p90 = percentile(ce_sorted, 90)
    p95 = percentile(ce_sorted, 95)
    max_ce = max(ce_list) if ce_list else 0
    max_ce_module = modules[ce_list.index(max_ce)] if ce_list else ""

    max_ca = 0
    max_ca_module = ""
    for m, v in ca.items():
        if v > max_ca:
            max_ca = v
            max_ca_module = m

    undirected: Dict[str, Set[str]] = {m: set() for m in modules}
    for src, tgts in deps_out.items():
        for tgt in tgts:
            undirected[src].add(tgt)
            undirected[tgt].add(src)

    comps = connected_components(modules, undirected)
    lcc = max((len(c) for c in comps), default=0)
    lcc_ratio = (lcc / n) if n else 0.0
    clustering = avg_clustering(modules, undirected)

    intra = 0
    for src, tgts in deps_out.items():
        g_src = slice_group(src)
        for tgt in tgts:
            if g_src == slice_group(tgt):
                intra += 1
    cohesion_ratio = (intra / edges) if edges else 0.0

    top_out = sorted(
        ((m, len(deps_out[m])) for m in modules), key=lambda x: (-x[1], x[0])
    )[:top_n]
    top_in = sorted(((m, ca.get(m, 0)) for m in modules), key=lambda x: (-x[1], x[0]))[
        :top_n
    ]

    return CouplingStats(
        modules=n,
        internal_edges=edges,
        avg_ce=avg_ce,
        median_ce=med_ce,
        p90_ce=float(p90),
        p95_ce=float(p95),
        max_ce=max_ce,
        max_ce_module=max_ce_module,
        max_ca=max_ca,
        max_ca_module=max_ca_module,
        lcc_ratio=float(lcc_ratio),
        avg_clustering=float(clustering),
        cohesion_ratio=float(cohesion_ratio),
        top_out=top_out,
        top_in=top_in,
    )
