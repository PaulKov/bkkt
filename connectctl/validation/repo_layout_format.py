from __future__ import annotations

from typing import List, Sequence

from .repo_layout_models import RepoLayoutIssue


def format_repo_layout_issues(
    issues: Sequence[RepoLayoutIssue],
    *,
    max_items: int = 20,
) -> str:
    """Human-friendly CLI output (non-markdown).

    We intentionally print only top-N findings to keep CI logs readable.
    The rest are collapsed as "... и ещё X".
    """

    if not issues:
        return "✅ Repo layout lint (connector_dir): проблем не найдено."

    max_items = int(max_items or 0)
    if max_items <= 0:
        max_items = 20

    ordered = sorted(issues, key=lambda x: (x.path, x.connector_dir))

    lines: List[str] = []
    warn_cnt = sum(1 for i in issues if i.severity == "warn")
    err_cnt = sum(1 for i in issues if i.severity != "warn")
    sev_tail = []
    if err_cnt:
        sev_tail.append(f"errors={err_cnt}")
    if warn_cnt:
        sev_tail.append(f"warns={warn_cnt}")
    sev_str = (" (" + ", ".join(sev_tail) + ")") if sev_tail else ""
    lines.append(
        f"⚠️ Repo layout lint (connector_dir): найдено проблем: {len(issues)}{sev_str}"
    )

    shown = ordered[:max_items]
    for i in shown:
        sev = "WARN" if i.severity == "warn" else "ERROR"
        lines.append(f"- [{sev}] {i.path}: {i.message}")
        if i.hint:
            lines.append(f"    hint: {i.hint}")

    if len(ordered) > max_items:
        more = len(ordered) - max_items
        lines.append(f"… и ещё {more} проблем(ы).")

    return "\n".join(lines)
