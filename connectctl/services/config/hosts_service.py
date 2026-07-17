from __future__ import annotations

import argparse
import socket
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List

from ...app.context import CliContext
from ...cli_helpers.repeatable_args import split_repeatable_csv
from ...cli_helpers.terminal_table import TableColumn, render_terminal_table
from ...exceptions import ConfigError
from ...logging_utils import get_logger
from ...models import Environment
from ...output import (
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
)
from .clusters_service import ConfigClustersService
from .endpoints import endpoint_matches
from .models import ConfigClusterEnvInventory
from .raw_loader import load_raw_config
from .selection import parse_cluster_group_filter, parse_env_filter
from .yaml_editor import RoundTripYamlEditor


class ConfigHostsService:
    """Plan/check/edit Connect REST hosts in `connectctl.yaml`."""

    def __init__(self, *, ctx: CliContext, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)

    def check(self, args: argparse.Namespace) -> int:
        fmt = resolve_output_format(args)
        timeout = float(getattr(args, "timeout_seconds", 5.0) or 5.0)
        result = self._selected_hosts_payload(args)
        checks = [
            _check_url(url, timeout_seconds=timeout)
            for scope in result["scopes"]
            for url in scope["connect_urls"]
        ]
        payload = {
            "operation": "check",
            "timeout_seconds": timeout,
            "checked_count": len(checks),
            "checks": [check.to_payload() for check in checks],
        }
        if is_machine_output(fmt):
            write_payload(payload, fmt=fmt)
        else:
            write_text(_render_checks_text(payload))
        return 0 if all(check.ok for check in checks) else 1

    def add(self, args: argparse.Namespace) -> int:
        return self._mutate_hosts(args, operation="add")

    def remove(self, args: argparse.Namespace) -> int:
        return self._mutate_hosts(args, operation="remove")

    def _selected_hosts_payload(self, args: argparse.Namespace) -> Dict[str, Any]:
        explicit_hosts = split_repeatable_csv(getattr(args, "connect_host", None))
        inventory = ConfigClustersService(
            ctx=self.ctx, logger=self.log
        ).build_inventory(
            group_filter=parse_cluster_group_filter(
                getattr(args, "cluster_group", None)
            ),
            env_filter=parse_env_filter(getattr(args, "env", None)),
            show_render_vars=False,
        )
        scopes: list[dict[str, Any]] = []
        for cluster in inventory.clusters:
            for env in cluster.envs:
                urls = _filter_urls(env=env, explicit_hosts=explicit_hosts)
                if explicit_hosts and not urls:
                    continue
                scopes.append(
                    {
                        "cluster_group": cluster.name,
                        "env": env.env.value,
                        "connect_hosts": [
                            host
                            for host in env.connect_hosts
                            if not explicit_hosts
                            or any(
                                endpoint_matches(item, (host,))
                                for item in explicit_hosts
                            )
                        ],
                        "connect_urls": urls,
                    }
                )
        return {"scopes": scopes}

    def _mutate_hosts(self, args: argparse.Namespace, *, operation: str) -> int:
        fmt = resolve_output_format(args)
        dry_run = bool(getattr(args, "dry_run", False))
        yes = bool(getattr(args, "yes", False))
        planned_hosts = split_repeatable_csv(getattr(args, "connect_host", None))
        if not planned_hosts:
            raise ConfigError("Provide at least one --connect-host value")

        cluster_group, env = _single_scope(args)
        _ensure_static_hosts_runtime(
            self.ctx, cluster_group=cluster_group, env=env, operation=operation
        )
        raw = load_raw_config(self.ctx.config_path, fs=self.ctx.fs)
        data = dict(raw.data)
        current_hosts = _get_raw_hosts(data, cluster_group=cluster_group, env=env)
        next_hosts = _next_hosts(
            current_hosts=current_hosts,
            planned_hosts=planned_hosts,
            operation=operation,
        )
        changed = next_hosts != current_hosts
        payload = {
            "operation": operation,
            "config_path": str(self.ctx.config_path),
            "cluster_group": cluster_group,
            "env": env.value,
            "dry_run": dry_run,
            "changed": changed,
            "current_hosts": current_hosts,
            "planned_hosts": planned_hosts,
            "next_hosts": next_hosts,
        }

        if changed and not dry_run:
            if not yes:
                raise ConfigError(
                    "Refusing to write connectctl.yaml without --yes. "
                    "Run with --dry-run first, then repeat with --yes."
                )
            RoundTripYamlEditor(fs=self.ctx.fs).mutate(
                self.ctx.config_path,
                lambda doc: _set_raw_hosts(
                    doc, cluster_group=cluster_group, env=env, hosts=next_hosts
                ),
            )

        if is_machine_output(fmt):
            write_payload(payload, fmt=fmt)
        else:
            write_text(_render_mutation_text(payload))
        return 0


@dataclass(frozen=True)
class _HealthCheck:
    url: str
    ok: bool
    status: str
    error: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "ok": self.ok,
            "status": self.status,
            "error": self.error,
        }


def _single_scope(args: argparse.Namespace) -> tuple[str, Environment]:
    groups = parse_cluster_group_filter(getattr(args, "cluster_group", None))
    envs = parse_env_filter(getattr(args, "env", None))
    if not groups or len(groups) != 1:
        raise ConfigError("config hosts add/remove requires exactly one --cluster")
    if not envs or len(envs) != 1:
        raise ConfigError("config hosts add/remove requires exactly one --env")
    return next(iter(groups)), next(iter(envs))


def _ensure_static_hosts_runtime(
    ctx: CliContext, *, cluster_group: str, env: Environment, operation: str
) -> None:
    try:
        cluster = ctx.settings.cluster_groups[cluster_group][env]
    except KeyError as exc:
        raise ConfigError(
            f"clusters.{cluster_group}.{env.value} not found in connectctl.yaml"
        ) from exc
    if cluster.runtime.is_static_hosts:
        return
    raise ConfigError(
        f"config hosts {operation} can edit only static_hosts runtimes. "
        f"`{cluster_group}` / `{env.value}` uses runtime.type={cluster.runtime.type!r} "
        f"with mutation_mode={cluster.runtime.mutation_mode!r}. "
        "Use `bkkt config runtimes explain` and update the runtime/CRD manifest instead."
    )


def _get_raw_hosts(
    data: Dict[str, Any], *, cluster_group: str, env: Environment
) -> list[str]:
    try:
        hosts = data["clusters"][cluster_group][env.value]["connect"]["hosts"]
    except KeyError as exc:
        raise ConfigError(
            f"clusters.{cluster_group}.{env.value}.connect.hosts not found"
        ) from exc
    if isinstance(hosts, str):
        return [item.strip() for item in hosts.split(",") if item.strip()]
    if isinstance(hosts, list):
        return [str(item) for item in hosts]
    raise ConfigError(
        f"clusters.{cluster_group}.{env.value}.connect.hosts must be list"
    )


def _set_raw_hosts(
    data: Dict[str, Any],
    *,
    cluster_group: str,
    env: Environment,
    hosts: list[str],
) -> None:
    data["clusters"][cluster_group][env.value]["connect"]["hosts"] = hosts


def _next_hosts(
    *, current_hosts: list[str], planned_hosts: list[str], operation: str
) -> list[str]:
    if operation == "add":
        out = list(current_hosts)
        seen = set(out)
        for host in planned_hosts:
            if host not in seen:
                out.append(host)
                seen.add(host)
        return out
    if operation == "remove":
        remove = set(planned_hosts)
        return [host for host in current_hosts if host not in remove]
    raise AssertionError(f"Unsupported operation: {operation}")


def _check_url(url: str, *, timeout_seconds: float) -> _HealthCheck:
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            return _HealthCheck(
                url=url,
                ok=200 <= int(response.status) < 500,
                status=str(response.status),
            )
    except (OSError, urllib.error.URLError, socket.timeout) as exc:
        return _HealthCheck(url=url, ok=False, status="error", error=str(exc))


def _filter_urls(
    *, env: ConfigClusterEnvInventory, explicit_hosts: list[str]
) -> list[str]:
    if not explicit_hosts:
        return list(env.connect_urls)
    return [
        url
        for url in env.connect_urls
        if any(endpoint_matches(item, (url,)) for item in explicit_hosts)
    ]


def _render_mutation_text(payload: Dict[str, Any]) -> str:
    mode = "DRY-RUN" if payload["dry_run"] else "WRITE"
    return (
        f"# BKKT: config hosts {payload['operation']} [{mode}]\n\n"
        f"- scope: `{payload['cluster_group']}` / `{payload['env']}`\n"
        f"- changed: `{payload['changed']}`\n"
        f"- current_hosts: `{', '.join(payload['current_hosts']) or '-'}`\n"
        f"- planned_hosts: `{', '.join(payload['planned_hosts'])}`\n"
        f"- next_hosts: `{', '.join(payload['next_hosts']) or '-'}`\n"
    )


def _render_checks_text(payload: Dict[str, Any]) -> str:
    rows: List[Dict[str, str]] = [
        {
            "url": item["url"],
            "ok": "yes" if item["ok"] else "no",
            "status": item["status"],
            "error": item.get("error") or "",
        }
        for item in payload["checks"]
    ]
    return (
        "# BKKT: config hosts check\n\n"
        + render_terminal_table(
            (
                TableColumn("url", "URL", max_width=48),
                TableColumn("ok", "Healthy", max_width=7),
                TableColumn("status", "Status", max_width=8),
                TableColumn("error", "Error", max_width=60),
            ),
            rows,
        )
        + "\n"
    )


__all__ = ["ConfigHostsService"]
