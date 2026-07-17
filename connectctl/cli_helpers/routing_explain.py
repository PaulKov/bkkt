from __future__ import annotations

from typing import Any, Mapping


def format_routing_explain_lines(debug: Mapping[str, Any]) -> list[str]:
    """Format routing debug payload (from ClusterRouter.route_with_debug) into human-readable lines.

    Designed for logging to stderr (BKKT LOG). Output is stable and grep-friendly.
    """

    lines: list[str] = []
    lines.append("Routing explain:")
    lines.append(f"  - default_cluster: {debug.get('default_cluster')}")
    if debug.get("cli_cluster"):
        lines.append(f"  - cli --cluster: {debug.get('cli_cluster')}")
    cc = debug.get("connectctl_cluster")
    if cc:
        src = debug.get("connectctl_cluster_source") or "(unknown)"
        lines.append(f"  - connectctl.cluster: {cc} (source: {src})")
    tags = debug.get("tags") or []
    if tags:
        lines.append("  - tags: " + ", ".join(str(t) for t in tags))
    assigns = debug.get("tag_cluster_assignments") or []
    if assigns:
        lines.append(
            "  - tag cluster assignments: " + ", ".join(f"{t}={v}" for t, v in assigns)
        )
        if debug.get("tag_cluster_conflict"):
            lines.append(f"  - tag conflict: {debug.get('tag_cluster_conflict')}")
    lines.append(
        f"  => chosen: {debug.get('selected_cluster')} (source={debug.get('selected_source')})"
    )
    return lines
