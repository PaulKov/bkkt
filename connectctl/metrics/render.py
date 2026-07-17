from __future__ import annotations

from typing import List, Tuple

from .models import CouplingStats, LocStats


def _grade(value: float, *, ok_max: float, warn_max: float) -> str:
    """Simple OK/WARN/ALERT grading for heuristics."""

    if value <= ok_max:
        return "OK"
    if value <= warn_max:
        return "WARN"
    return "ALERT"


def _ratio(loc: int, sloc: int) -> str:
    if sloc <= 0:
        return "n/a"
    return f"{loc / sloc:.2f}"


def render_loc_table_md(stats: LocStats) -> str:
    if not stats.top:
        return "(no files)\n"
    lines: List[str] = []
    lines.append("| Module | LOC | SLOC |\n")
    lines.append("|---|---:|---:|\n")
    for path, loc, sloc in stats.top:
        lines.append(f"| `{path}` | {loc} | {sloc} |\n")
    return "".join(lines)


def render_top_list_md(items: List[Tuple[str, int]]) -> str:
    return "\n".join([f"- `{m}`: **{v}**" for m, v in items]) + ("\n" if items else "")


def build_metrics_block_md(
    *,
    start_marker: str,
    end_marker: str,
    repo_loc: LocStats,
    repo_non_test_loc: LocStats,
    connectctl_loc: LocStats,
    coupling: CouplingStats,
) -> str:
    parts: List[str] = []
    parts.append(f"{start_marker}\n")
    parts.append(
        "_The section below is generated automatically by `bkkt docs update-dev-metrics`._\n\n"
    )

    parts.append("### Repository Python footprint\n\n")
    parts.append("**All Python files (`**/*.py`)**\n\n")
    parts.append(
        "- Files: **{files}**\n"
        "- LOC: **{total}**\n"
        "- SLOC: **{sloc}**\n"
        "- LOC/SLOC ratio: **{ratio}**\n"
        "- Smallest file by LOC: **{min}** (`{min_path}`)\n"
        "- Largest file by LOC: **{max}** (`{max_path}`)\n"
        "- Average LOC/file: **{avg:.2f}**\n"
        "- Median LOC/file: **{med:.0f}**\n\n".format(
            files=repo_loc.files,
            total=repo_loc.total_lines,
            sloc=repo_loc.total_sloc,
            ratio=_ratio(repo_loc.total_lines, repo_loc.total_sloc),
            min=repo_loc.min_lines,
            min_path=repo_loc.min_path,
            max=repo_loc.max_lines,
            max_path=repo_loc.max_path,
            avg=repo_loc.avg_lines,
            med=repo_loc.median_lines,
        )
    )

    parts.append("**Python files excluding tests**\n\n")
    parts.append(
        "- Files: **{files}**\n"
        "- LOC: **{total}**\n"
        "- SLOC: **{sloc}**\n"
        "- LOC/SLOC ratio: **{ratio}**\n\n".format(
            files=repo_non_test_loc.files,
            total=repo_non_test_loc.total_lines,
            sloc=repo_non_test_loc.total_sloc,
            ratio=_ratio(repo_non_test_loc.total_lines, repo_non_test_loc.total_sloc),
        )
    )

    parts.append("### `connectctl` package footprint\n\n")
    parts.append(
        "- Files: **{files}**\n"
        "- LOC: **{total}**\n"
        "- SLOC: **{sloc}**\n"
        "- LOC/SLOC ratio: **{ratio}**\n"
        "- Average LOC/file: **{avg:.2f}**\n"
        "- Median LOC/file: **{med:.0f}**\n"
        "- Average SLOC/file: **{avg_sloc:.2f}**\n"
        "- Median SLOC/file: **{med_sloc:.0f}**\n\n".format(
            files=connectctl_loc.files,
            total=connectctl_loc.total_lines,
            sloc=connectctl_loc.total_sloc,
            ratio=_ratio(connectctl_loc.total_lines, connectctl_loc.total_sloc),
            avg=connectctl_loc.avg_lines,
            med=connectctl_loc.median_lines,
            avg_sloc=connectctl_loc.avg_sloc,
            med_sloc=connectctl_loc.median_sloc,
        )
    )

    parts.append(f"**Top {len(connectctl_loc.top)} largest `connectctl` modules**\n\n")
    parts.append(render_loc_table_md(connectctl_loc))
    parts.append("\n")

    parts.append("### Coupling / cohesion (`connectctl.*` internal imports)\n\n")
    parts.append(
        "- Modules: **{modules}**\n"
        "- Internal import edges: **{edges}**\n"
        "- Average Ce (fan-out): **{avg:.2f}**\n"
        "- Median Ce: **{med:.0f}**\n"
        "- P90 Ce: **{p90:.0f}**\n"
        "- P95 Ce: **{p95:.0f}**\n"
        "- Max Ce: **{max_ce}** (`{max_ce_module}`)\n"
        "- Max Ca (fan-in): **{max_ca}** (`{max_ca_module}`)\n"
        "- Largest connected component ratio: **{lcc:.3f}**\n"
        "- Average clustering coefficient: **{cl:.3f}**\n"
        "- Cohesion ratio: **{coh:.3f}**\n\n".format(
            modules=coupling.modules,
            edges=coupling.internal_edges,
            avg=coupling.avg_ce,
            med=coupling.median_ce,
            p90=coupling.p90_ce,
            p95=coupling.p95_ce,
            max_ce=coupling.max_ce,
            max_ce_module=coupling.max_ce_module,
            max_ca=coupling.max_ca,
            max_ca_module=coupling.max_ca_module,
            lcc=coupling.lcc_ratio,
            cl=coupling.avg_clustering,
            coh=coupling.cohesion_ratio,
        )
    )

    ce_grade = _grade(coupling.avg_ce, ok_max=5.0, warn_max=10.0)
    p90_grade = _grade(coupling.p90_ce, ok_max=10.0, warn_max=15.0)
    cl_grade = _grade(coupling.avg_clustering, ok_max=0.15, warn_max=0.25)
    parts.append("**Heuristic interpretation**\n\n")
    parts.append(
        "- Average Ce = **{avg:.2f}** → **{ce}**\n"
        "- P90 Ce = **{p90:.0f}** → **{p90g}**\n"
        "- Average clustering = **{cl:.3f}** → **{clg}**\n\n".format(
            avg=coupling.avg_ce,
            ce=ce_grade,
            p90=coupling.p90_ce,
            p90g=p90_grade,
            cl=coupling.avg_clustering,
            clg=cl_grade,
        )
    )

    parts.append(f"**Top {len(coupling.top_out)} modules by fan-out (Ce)**\n\n")
    parts.append(render_top_list_md(coupling.top_out))
    parts.append("\n")
    parts.append(f"**Top {len(coupling.top_in)} modules by fan-in (Ca)**\n\n")
    parts.append(render_top_list_md(coupling.top_in))
    parts.append(f"{end_marker}")
    return "".join(parts)
