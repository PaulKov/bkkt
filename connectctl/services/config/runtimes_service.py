from __future__ import annotations

import argparse
from typing import Any, Dict, List

from ...cli_helpers.terminal_table import (
    TableColumn,
    format_lines,
    render_terminal_table,
)
from ...exceptions import ConfigError
from ...logging_utils import get_logger
from ...output import (
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
)
from .clusters_service import ConfigClustersService
from .models import ConfigClusterEnvInventory
from .selection import parse_cluster_group_filter, parse_env_filter


class ConfigRuntimesService:
    """List, explain and statically check Kafka Connect runtime definitions."""

    def __init__(self, *, ctx, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or getattr(ctx, "logger", None))

    def list(self, args: argparse.Namespace) -> int:
        fmt = resolve_output_format(args)
        rows = self._runtime_rows(args)
        payload: Dict[str, Any] = {
            "runtime_count": len(rows),
            "runtimes": [_row_payload(row) for row in rows],
        }
        if is_machine_output(fmt):
            write_payload(payload, fmt=fmt)
        else:
            write_text(_render_list_text(payload["runtimes"]))
        return 0

    def explain(self, args: argparse.Namespace) -> int:
        fmt = resolve_output_format(args)
        rows = self._runtime_rows(args)
        if not rows:
            raise ConfigError("No runtime scopes matched the selected --cluster/--env")
        if len(rows) != 1:
            raise ConfigError(
                "config runtimes explain requires exactly one scope. "
                "Pass one --cluster and one --env."
            )
        payload = _row_payload(rows[0])
        payload["checks"] = [_check_row(rows[0])]
        if is_machine_output(fmt):
            write_payload(payload, fmt=fmt)
        else:
            write_text(_render_explain_text(payload))
        return 0

    def check(self, args: argparse.Namespace) -> int:
        fmt = resolve_output_format(args)
        rows = self._runtime_rows(args)
        checks = [_check_row(row) for row in rows]
        payload = {
            "ok": not any(check["status"] == "error" for check in checks),
            "check_count": len(checks),
            "checks": checks,
        }
        if is_machine_output(fmt):
            write_payload(payload, fmt=fmt)
        else:
            write_text(_render_check_text(checks))
        return 0 if payload["ok"] else 1

    def _runtime_rows(self, args: argparse.Namespace) -> List["_RuntimeRow"]:
        inventory = ConfigClustersService(
            ctx=self.ctx, logger=self.log
        ).build_inventory(
            group_filter=parse_cluster_group_filter(
                getattr(args, "cluster_group", None)
            ),
            env_filter=parse_env_filter(getattr(args, "env", None)),
            show_render_vars=False,
        )
        rows: List[_RuntimeRow] = []
        for cluster in inventory.clusters:
            for env in cluster.envs:
                rows.append(_RuntimeRow(cluster_group=cluster.name, env=env))
        return rows


class _RuntimeRow:
    def __init__(self, *, cluster_group: str, env: ConfigClusterEnvInventory) -> None:
        self.cluster_group = cluster_group
        self.env = env


def _row_payload(row: _RuntimeRow) -> Dict[str, Any]:
    env = row.env
    return {
        "cluster_group": row.cluster_group,
        "env": env.env.value,
        "runtime": {
            "type": env.runtime_type,
            "operator_managed": env.runtime_operator_managed,
            "mutation_mode": env.runtime_mutation_mode,
            "rest_access": env.runtime_rest_access,
            "kubernetes_context": env.runtime_kubernetes_context,
            "kubernetes_namespace": env.runtime_kubernetes_namespace,
            "service": env.runtime_service,
            "pod_selector": env.runtime_pod_selector,
            "resource_name": env.runtime_resource_name,
            "connector_label_selector": env.runtime_connector_label_selector,
            "provider": env.runtime_provider,
            "limitations": list(env.runtime_limitations),
        },
        "connect_urls": list(env.connect_urls),
        "connect_hosts": list(env.connect_hosts),
    }


def _check_row(row: _RuntimeRow) -> Dict[str, Any]:
    env = row.env
    messages: list[str] = []
    status = "ok"
    if env.runtime_type == "static_hosts":
        if not env.connect_urls:
            status = "error"
            messages.append("static_hosts runtime has no Connect REST URLs")
    elif env.runtime_type == "k8s_rest":
        status = "limited"
        messages.extend(_kubernetes_messages(env))
        if env.runtime_rest_access == "port_forward" and not env.connect_urls:
            messages.append("REST diagnostics require kubectl port-forward")
    elif env.runtime_type in {"strimzi", "confluent_kubernetes"}:
        status = "limited"
        messages.extend(_kubernetes_messages(env))
        if not env.runtime_resource_name:
            status = "error"
            messages.append("operator runtime resource name is not configured")
        messages.append(
            "CRD status/apply requires Kubernetes API access; REST mutations are guarded"
        )
    else:
        status = "limited"
        messages.append("managed_connect is read-only in this BKKT release")
    if env.runtime_limitations:
        messages.extend(env.runtime_limitations)
    return {
        "cluster_group": row.cluster_group,
        "env": env.env.value,
        "runtime_type": env.runtime_type,
        "status": status,
        "messages": messages,
    }


def _kubernetes_messages(env: ConfigClusterEnvInventory) -> list[str]:
    messages: list[str] = []
    if not env.runtime_kubernetes_namespace:
        messages.append("kubernetes.namespace is not configured")
    if not env.runtime_kubernetes_context:
        messages.append(
            "kubernetes.context is not configured; BKKT will use the active kube context"
        )
    return messages


def _render_list_text(items: list[Dict[str, Any]]) -> str:
    rows = [_runtime_text_row(item) for item in items]
    return (
        "# BKKT: Kafka Connect runtimes\n\n"
        + render_terminal_table(_runtime_columns(), rows)
        + "\n"
    )


def _render_explain_text(payload: Dict[str, Any]) -> str:
    runtime = payload["runtime"]
    lines = [
        "# BKKT: Kafka Connect runtime\n",
        f"- cluster: `{payload['cluster_group']}` / `{payload['env']}`",
        f"- type: `{runtime['type']}`",
        f"- operator_managed: `{runtime['operator_managed']}`",
        f"- mutation_mode: `{runtime['mutation_mode']}`",
        f"- rest_access: `{runtime['rest_access']}`",
        f"- connect_urls: `{', '.join(payload['connect_urls']) or '-'}`",
    ]
    check = payload["checks"][0]
    if check["messages"]:
        lines.append("\n## Notes\n")
        lines.extend(f"- {message}" for message in check["messages"])
    return "\n".join(lines) + "\n"


def _render_check_text(checks: list[Dict[str, Any]]) -> str:
    rows: List[Dict[str, str]] = [
        {
            "cluster": item["cluster_group"],
            "env": item["env"],
            "runtime": item["runtime_type"],
            "status": item["status"],
            "messages": format_lines(item["messages"]) if item["messages"] else "-",
        }
        for item in checks
    ]
    return (
        "# BKKT: Kafka Connect runtime checks\n\n"
        + render_terminal_table(
            (
                TableColumn("cluster", "Cluster group", max_width=36),
                TableColumn("env", "Env", max_width=6),
                TableColumn("runtime", "Runtime", max_width=22),
                TableColumn("status", "Status", max_width=10),
                TableColumn("messages", "Messages", max_width=64),
            ),
            rows,
        )
        + "\n"
    )


def _runtime_text_row(item: Dict[str, Any]) -> Dict[str, str]:
    runtime = item["runtime"]
    return {
        "cluster": item["cluster_group"],
        "env": item["env"],
        "runtime": runtime["type"],
        "managed": "yes" if runtime["operator_managed"] else "no",
        "mutation": runtime["mutation_mode"],
        "rest": runtime["rest_access"],
        "k8s": format_lines(
            [
                value
                for value in (
                    runtime["kubernetes_context"],
                    runtime["kubernetes_namespace"],
                )
                if value
            ]
        )
        or "-",
        "resource": format_lines(
            [
                value
                for value in (
                    runtime["resource_name"],
                    runtime["service"],
                    runtime["provider"],
                )
                if value
            ]
        )
        or "-",
    }


def _runtime_columns() -> tuple[TableColumn, ...]:
    return (
        TableColumn("cluster", "Cluster group", max_width=36),
        TableColumn("env", "Env", max_width=6),
        TableColumn("runtime", "Runtime", max_width=22),
        TableColumn("managed", "Operator", max_width=8),
        TableColumn("mutation", "Mutation", max_width=12),
        TableColumn("rest", "REST access", max_width=14),
        TableColumn("k8s", "K8s", max_width=28),
        TableColumn("resource", "Runtime resource", max_width=32),
    )


__all__ = ["ConfigRuntimesService"]
