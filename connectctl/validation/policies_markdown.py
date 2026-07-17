from __future__ import annotations

from typing import List, Sequence

from .policies_models import PolicyIssue


def build_policies_lint_markdown(issues: Sequence[PolicyIssue]) -> str:
    if not issues:
        return "✅ **Policy lint:** no issues found."

    lines: List[str] = []
    lines.append("### Policy lint")
    lines.append("")
    lines.append("| Severity | Policy | Manifest | File | Key | Message | Hint |")
    lines.append("|---|---|---|---|---|---|---|")

    for i in issues:
        sev = "❌ error" if i.severity == "error" else "⚠️ warn"
        man = f"`{i.manifest_path}`"
        fp = f"`{i.file_path}`" if i.file_path else "-"
        key = f"`{i.key}`" if i.key else "-"
        msg = i.message.replace("\n", " ")
        hint = (i.hint or "-").replace("\n", " ")
        lines.append(
            f"| {sev} | `{i.policy}` | {man} | {fp} | {key} | {msg} | {hint} |"
        )

    return "\n".join(lines)
