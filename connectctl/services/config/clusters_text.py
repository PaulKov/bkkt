from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import List, Sequence

from ...cli_helpers.terminal_table import (
    TableColumn,
    format_lines,
    render_terminal_table,
)
from .models import ConfigClusterEnvInventory, ConfigClustersResult


@dataclass(frozen=True)
class ClusterDisplayOptions:
    view: str = "long"
    hide_kafka_bootstrap: bool = False
    hide_schema_registry: bool = False
    no_provenance: bool = False

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "ClusterDisplayOptions":
        return cls(
            view=str(getattr(args, "view", "long") or "long"),
            hide_kafka_bootstrap=bool(getattr(args, "hide_kafka_bootstrap", False)),
            hide_schema_registry=bool(getattr(args, "hide_schema_registry", False)),
            no_provenance=bool(getattr(args, "no_provenance", False)),
        )


def build_clusters_text(
    result: ConfigClustersResult,
    *,
    show_render_vars: bool,
    display: ClusterDisplayOptions,
) -> str:
    lines: List[str] = []
    lines.append("# BKKT: configured clusters\n")
    lines.append(f"- config: `{result.config_path}`")
    lines.append(f"- default_cluster: `{result.default_cluster}`")
    lines.append(f"- selected cluster groups: {len(result.clusters)}")
    lines.append(
        f"- selected env scopes: {sum(len(c.envs) for c in result.clusters)}\n"
    )
    lines.append(render_terminal_table(_table_columns(display), _table_rows(result)))
    notes = [] if display.no_provenance else _inventory_notes(result)
    if notes:
        lines.append("\n## Notes\n")
        lines.extend(f"- {note}" for note in notes)
    if show_render_vars:
        lines.append("")
        lines.extend(_render_vars_section(result))
    return "\n".join(lines) + "\n"


def _table_rows(result: ConfigClustersResult) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for cluster in result.clusters:
        for env in cluster.envs:
            rows.append(
                {
                    "cluster": cluster.name,
                    "default": "yes" if cluster.is_default else "",
                    "env": env.env.value,
                    "lifecycle": _fmt_lifecycle_cell(env),
                    "runtime": env.runtime_type,
                    "operator": (
                        "operator-managed"
                        if env.runtime_operator_managed
                        else "self-managed"
                    ),
                    "mutation": env.runtime_mutation_mode,
                    "k8s": _fmt_runtime_k8s(env),
                    "resource": _fmt_runtime_resource(env),
                    "rest_access": env.runtime_rest_access,
                    "connect_hosts": _fmt_seq(env.connect_hosts),
                    "connect_urls": _fmt_seq(env.connect_urls),
                    "kafka": _fmt_inventory_cell(
                        env.kafka_bootstrap_servers,
                        empty_label=(
                            "worker-managed"
                            if env.kafka_bootstrap_source == "worker-managed"
                            else "-"
                        ),
                    ),
                    "schema_registry": _fmt_inventory_cell(
                        env.schema_registry_urls,
                        empty_label=(
                            "pruned" if env.schema_registry_source == "pruned" else "-"
                        ),
                    ),
                }
            )
    return rows


def _table_columns(display: ClusterDisplayOptions) -> tuple[TableColumn, ...]:
    columns: list[TableColumn] = [
        TableColumn("cluster", "Cluster group", max_width=44),
        TableColumn("default", "Default", max_width=7),
        TableColumn("env", "Env", max_width=5),
        TableColumn("lifecycle", "Lifecycle", max_width=24),
        TableColumn("runtime", "Runtime", max_width=20),
        TableColumn("operator", "Managed", max_width=18),
        TableColumn("connect_hosts", "Connect hosts", max_width=24),
    ]
    if display.view == "details":
        columns.extend(
            [
                TableColumn("mutation", "Mutation", max_width=12),
                TableColumn("k8s", "K8s", max_width=28),
                TableColumn("resource", "Runtime resource", max_width=32),
                TableColumn("rest_access", "REST access", max_width=14),
            ]
        )
    if display.view != "short":
        columns.append(TableColumn("connect_urls", "Connect URLs", max_width=36))
    if not display.hide_kafka_bootstrap:
        columns.append(TableColumn("kafka", "Kafka bootstrap", max_width=42))
    if not display.hide_schema_registry:
        columns.append(TableColumn("schema_registry", "Schema Registry", max_width=42))
    return tuple(columns)


def _inventory_notes(result: ConfigClustersResult) -> list[str]:
    notes: list[str] = []
    for cluster in result.clusters:
        for env in cluster.envs:
            prefix = f"`{cluster.name}` / `{env.env.value}`"
            if env.kafka_bootstrap_source and env.kafka_bootstrap_servers:
                notes.append(
                    f"{prefix}: Kafka bootstrap from {env.kafka_bootstrap_source}."
                )
            if env.schema_registry_source and env.schema_registry_urls:
                notes.append(
                    f"{prefix}: Schema Registry from {env.schema_registry_source}."
                )
            if env.runtime_limitations:
                notes.extend(
                    f"{prefix}: runtime limitation: {limitation}"
                    for limitation in env.runtime_limitations
                )
            if env.lifecycle.disabled:
                notes.append(f"{prefix}: {_fmt_lifecycle_note(env)}.")
            notes.extend(f"{prefix}: {note}." for note in env.notes)
    return notes


def _render_vars_section(result: ConfigClustersResult) -> List[str]:
    lines: List[str] = ["## Render details\n"]
    for cluster in result.clusters:
        for env in cluster.envs:
            details: List[str] = []
            if env.render_prune_config_keys:
                details.append(
                    f"prune={', '.join(f'`{key}`' for key in env.render_prune_config_keys)}"
                )
            if env.render_vars:
                rendered_vars = ", ".join(
                    f"`{key}`={value!r}"
                    for key, value in sorted(env.render_vars.items())
                )
                details.append(f"vars={rendered_vars}")
            if details:
                lines.append(
                    f"- `{cluster.name}` / `{env.env.value}`: {'; '.join(details)}"
                )
    if len(lines) == 1:
        lines.append("- No render vars or prune keys in selected scopes.")
    lines.append("")
    return lines


def _fmt_seq(values: Sequence[str]) -> str:
    if not values:
        return "-"
    return format_lines(values)


def _fmt_lifecycle_cell(env: ConfigClusterEnvInventory) -> str:
    if not env.lifecycle.disabled:
        return "enabled"
    parts = ["disabled"]
    if env.lifecycle.ticket:
        parts.append(env.lifecycle.ticket)
    return "\n".join(parts)


def _fmt_lifecycle_note(env: ConfigClusterEnvInventory) -> str:
    parts = [f"lifecycle disabled: {env.lifecycle.reason or 'no reason provided'}"]
    if env.lifecycle.ticket:
        parts.append(f"ticket={env.lifecycle.ticket}")
    if env.lifecycle.until:
        parts.append(f"until={env.lifecycle.until}")
    return "; ".join(parts)


def _fmt_inventory_cell(values: Sequence[str], *, empty_label: str) -> str:
    if values:
        return format_lines(values)
    return empty_label


def _fmt_runtime_k8s(env: ConfigClusterEnvInventory) -> str:
    parts = [
        item
        for item in (
            env.runtime_kubernetes_context,
            env.runtime_kubernetes_namespace,
        )
        if item
    ]
    return "\n".join(parts) if parts else "-"


def _fmt_runtime_resource(env: ConfigClusterEnvInventory) -> str:
    parts = [
        item
        for item in (
            env.runtime_resource_name,
            env.runtime_service,
            env.runtime_provider,
        )
        if item
    ]
    return "\n".join(parts) if parts else "-"
