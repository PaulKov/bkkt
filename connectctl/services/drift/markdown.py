from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from ...models import Environment


def build_drift_markdown(
    *,
    env: Environment,
    manifests_checked: int,
    ok_count: int,
    disabled_skipped: int,
    drift_count: int,
    missing_count: int,
    group_stats_dt,
    group_stats_dts,
    drift_key_counter: Counter[str],
    drift_override_source_counter: Counter[str],
    detailed: List[Dict[str, Any]],
    include_diffs: bool,
    max_lines: int,
    top_n: int,
    tool_name: str = "BKKT",
) -> str:
    """Build a markdown drift report.

    The report is suitable for local output and CI logs.
    """

    lines: List[str] = []
    lines.append(f"## {tool_name} drift ({env.value})")
    lines.append("")
    lines.append(f"- Manifests checked: **{manifests_checked}**")
    lines.append(f"- In sync: **{ok_count}**")
    lines.append(f"- Disabled skipped: **{disabled_skipped}**")
    lines.append(f"- Drifted: **{drift_count}**")
    lines.append(f"- Missing in cluster: **{missing_count}**")
    lines.append("- Comparison mode: **post-prune**")
    if any(e.get("pruned_config_keys") for e in detailed):
        lines.append(
            "- Note: cluster render policy excluded some config keys before comparison"
        )

    if group_stats_dt:
        lines.append("")
        lines.append("### Summary by domain / type")
        lines.append("")
        lines.append("| Group | Total | In sync | Drifted | Missing |")
        lines.append("|---|---:|---:|---:|---:|")
        for group_key in sorted(group_stats_dt.keys()):
            s = group_stats_dt[group_key]
            lines.append(
                f"| `{group_key}` | {s['total']} | {s['ok']} | {s['drift']} | {s['missing']} |"
            )

    if group_stats_dts:
        lines.append("")
        lines.append("### Summary by domain / type / system")
        lines.append("")
        lines.append("| Group | Total | In sync | Drifted | Missing |")
        lines.append("|---|---:|---:|---:|---:|")
        for group_key in sorted(group_stats_dts.keys()):
            s = group_stats_dts[group_key]
            lines.append(
                f"| `{group_key}` | {s['total']} | {s['ok']} | {s['drift']} | {s['missing']} |"
            )

    if drift_key_counter:
        lines.append("")
        lines.append(f"### Top drift reasons (by config key, top {top_n})")
        lines.append("")
        for k, cnt in drift_key_counter.most_common(top_n):
            lines.append(f"- `{k}`: **{cnt}**")

    if drift_override_source_counter:
        lines.append("")
        lines.append(f"### Top override sources (by layer file, top {top_n})")
        lines.append("")
        lines.append(
            "_(Counts exclude base/env manifest files; focuses on shared overrides.)_"
        )
        lines.append("")
        for rel_lp, cnt in drift_override_source_counter.most_common(top_n):
            lines.append(f"- `{rel_lp}`: **{cnt}**")

    if detailed:
        lines.append("")
        lines.append("### Details")
        for e in detailed:
            name = str(e["name"])
            status = str(e["status"])
            rel = str(e.get("manifest_rel") or "")
            url = e.get("manifest_url")
            manifest_md = f"[{rel}]({url})" if url else f"`{rel}`"

            lines.append("")
            lines.append(f"#### `{name}`")
            lines.append("")
            lines.append(f"- Status: **{status}**")
            lines.append(
                f"- Domain/type/system: `{e.get('domain')}` / `{e.get('type')}` / `{e.get('system')}`"
            )
            lines.append(f"- Manifest: {manifest_md}")

            if status == "disabled":
                lines.append(
                    f"- Reason: `{e.get('reason') or 'disabled via connectctl.lifecycle'}`"
                )
                if e.get("ticket"):
                    lines.append(f"- Ticket: `{e.get('ticket')}`")
                if e.get("until"):
                    lines.append(f"- Until: `{e.get('until')}`")
            elif status == "drift":
                keys = list(e.get("diff_keys") or [])
                if keys:
                    lines.append(
                        f"- Different keys: {', '.join(f'`{k}`' for k in keys[:50])}"
                    )
                    if len(keys) > 50:
                        lines.append(f"  - _(and {len(keys) - 50} more)_")

                pruned = list(e.get("pruned_config_keys") or [])
                if pruned:
                    lines.append(
                        f"- Pruned before compare: {', '.join(f'`{k}`' for k in pruned)}"
                    )

                if include_diffs and e.get("diff"):
                    if e.get("diff_trimmed"):
                        lines.append("\n_(diff truncated; increase with --max-lines)_")
                    lines.append("\n```diff")
                    lines.append(str(e["diff"]).rstrip())
                    lines.append("```")

    if drift_count == 0 and missing_count == 0 and disabled_skipped == 0:
        lines.append("")
        lines.append("✅ No drift detected")

    return "\n".join(lines) + "\n"
