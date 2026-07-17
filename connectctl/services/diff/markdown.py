from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from ...models import Environment

from .models import DisabledItem, DriftItem, MissingItem


def build_diff_markdown(
    *,
    env: Environment,
    total: int,
    clean: int,
    disabled: List[DisabledItem],
    missing: List[MissingItem],
    drifted: Iterable[DriftItem],
    cluster_stats: Dict[str, Dict[str, int]],
) -> str:
    """Сформировать Markdown отчёт diff.

    В multi-cluster режиме выводит агрегаты по каждому cluster group.
    """

    drifted_list = list(drifted)
    clusters = sorted(cluster_stats.keys())
    multi = len(clusters) > 1
    single_cluster = clusters[0] if clusters else None

    lines: List[str] = []
    lines.append(f"## connectctl diff ({env.value})")
    lines.append("")
    lines.append(f"- Manifests checked: **{total}**")
    lines.append(f"- In sync: **{clean}**")
    lines.append(f"- Disabled skipped: **{len(disabled)}**")
    lines.append(f"- Drifted: **{len(drifted_list)}**")
    lines.append(f"- Missing in cluster: **{len(missing)}**")
    lines.append("- Comparison mode: **post-prune**")
    if any(item.pruned_config_keys for item in drifted_list):
        lines.append(
            "- Note: cluster render policy excluded some config keys before comparison"
        )

    if multi:
        lines.append("")
        lines.append("### Кластера")
        lines.append("")
        lines.append(
            "| cluster group | checked | in sync | disabled skipped | drifted | missing |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|")
        for c in clusters:
            st = cluster_stats.get(c, {})
            lines.append(
                f"| `{c}` | {int(st.get('checked', 0))} | {int(st.get('clean', 0))} | {int(st.get('disabled', 0))} | {int(st.get('drifted', 0))} | {int(st.get('missing', 0))} |"
            )

    if disabled:
        lines.append("")
        lines.append("### Disabled")

        by_cluster_disabled: Dict[str, List[DisabledItem]] = defaultdict(list)
        for item in disabled:
            by_cluster_disabled[item.cluster].append(item)

        if multi:
            for c in clusters:
                disabled_items = sorted(
                    by_cluster_disabled.get(c, []), key=lambda item: item.name
                )
                if not disabled_items:
                    continue
                lines.append("")
                lines.append(f"#### `{c}`")
                for item in disabled_items:
                    extra = []
                    if item.ticket:
                        extra.append(f"ticket `{item.ticket}`")
                    if item.until:
                        extra.append(f"until `{item.until}`")
                    suffix = f" ({', '.join(extra)})" if extra else ""
                    lines.append(
                        f"- `{item.name}` from `{item.manifest_rel}`: {item.reason}{suffix}"
                    )
        elif single_cluster is not None:
            for item in sorted(
                by_cluster_disabled.get(single_cluster, []), key=lambda x: x.name
            ):
                extra = []
                if item.ticket:
                    extra.append(f"ticket `{item.ticket}`")
                if item.until:
                    extra.append(f"until `{item.until}`")
                suffix = f" ({', '.join(extra)})" if extra else ""
                lines.append(
                    f"- `{item.name}` from `{item.manifest_rel}`: {item.reason}{suffix}"
                )

    # Missing
    if missing:
        lines.append("")
        lines.append("### Missing")

        by_cluster_missing: Dict[str, List[str]] = defaultdict(list)
        for m in missing:
            by_cluster_missing[m.cluster].append(m.name)

        if multi:
            for c in clusters:
                names = sorted(by_cluster_missing.get(c, []))
                if not names:
                    continue
                lines.append("")
                lines.append(f"#### `{c}`")
                for n in names:
                    lines.append(f"- `{n}`")
        elif single_cluster is not None:
            for n in sorted(by_cluster_missing.get(single_cluster, [])):
                lines.append(f"- `{n}`")

    # Drift
    if drifted_list:
        lines.append("")
        lines.append("### Drift")

        by_cluster_drift: Dict[str, List[DriftItem]] = defaultdict(list)
        for d in drifted_list:
            by_cluster_drift[d.cluster].append(d)

        if multi:
            for c in clusters:
                drift_items = sorted(by_cluster_drift.get(c, []), key=lambda x: x.name)
                if not drift_items:
                    continue
                lines.append("")
                lines.append(f"#### `{c}`")
                for drift_item in drift_items:
                    lines.append("")
                    lines.append(f"##### `{drift_item.name}`")
                    lines.append("")
                    lines.append(f"_Manifest: `{drift_item.manifest_rel}`_")
                    if drift_item.pruned_config_keys:
                        keys = ", ".join(
                            f"`{k}`" for k in drift_item.pruned_config_keys
                        )
                        lines.append(f"_Pruned before compare: {keys}_")
                    if drift_item.trimmed:
                        lines.append("_(diff truncated; increase with --max-lines)_")
                    lines.append("```diff")
                    lines.append(drift_item.diff.rstrip())
                    lines.append("```")
        elif single_cluster is not None:
            drift_items = sorted(
                by_cluster_drift.get(single_cluster, []), key=lambda x: x.name
            )
            for drift_item in drift_items:
                lines.append("")
                lines.append(f"#### `{drift_item.name}`")
                lines.append("")
                lines.append(f"_Manifest: `{drift_item.manifest_rel}`_")
                if drift_item.pruned_config_keys:
                    keys = ", ".join(f"`{k}`" for k in drift_item.pruned_config_keys)
                    lines.append(f"_Pruned before compare: {keys}_")
                if drift_item.trimmed:
                    lines.append("_(diff truncated; increase with --max-lines)_")
                lines.append("```diff")
                lines.append(drift_item.diff.rstrip())
                lines.append("```")

    if not missing and not drifted_list and not disabled:
        lines.append("")
        lines.append("✅ No drift detected")

    return "\n".join(lines) + "\n"
