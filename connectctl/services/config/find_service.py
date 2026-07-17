from __future__ import annotations

import argparse
from typing import Any, Dict, List

from ...app.context import CliContext
from ...cli_helpers.repeatable_args import split_repeatable_csv
from ...cli_helpers.terminal_table import TableColumn, render_terminal_table
from ...logging_utils import get_logger
from ...output import (
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
)
from .clusters_service import ConfigClustersService
from .endpoints import endpoint_matches
from .models import ConfigClusterEnvInventory
from .selection import parse_cluster_group_filter, parse_env_filter


class ConfigFindService:
    """Find connectctl cluster scopes by Connect/Kafka/Schema Registry endpoints."""

    def __init__(self, *, ctx: CliContext, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)

    def run(self, args: argparse.Namespace) -> int:
        fmt = resolve_output_format(args)
        group_filter = parse_cluster_group_filter(getattr(args, "cluster_group", None))
        env_filter = parse_env_filter(getattr(args, "env", None))
        query = _FindQuery.from_args(args)
        inventory = ConfigClustersService(
            ctx=self.ctx, logger=self.log
        ).build_inventory(
            group_filter=group_filter,
            env_filter=env_filter,
            show_render_vars=False,
        )

        matches: list[dict[str, Any]] = []
        for cluster in inventory.clusters:
            for env in cluster.envs:
                matched_by = _matched_by(query, env)
                if matched_by or query.is_empty:
                    matches.append(
                        {
                            "cluster_group": cluster.name,
                            "is_default": cluster.is_default,
                            "env": env.env.value,
                            "connect_hosts": list(env.connect_hosts),
                            "connect_urls": list(env.connect_urls),
                            "kafka_bootstrap_servers": list(
                                env.kafka_bootstrap_servers
                            ),
                            "kafka_bootstrap_source": env.kafka_bootstrap_source,
                            "schema_registry_urls": list(env.schema_registry_urls),
                            "schema_registry_source": env.schema_registry_source,
                            "matched_by": matched_by or ["all"],
                            "notes": list(env.notes),
                        }
                    )

        payload = {
            "config_path": str(inventory.config_path),
            "query": query.to_payload(),
            "match_count": len(matches),
            "matches": matches,
        }
        if is_machine_output(fmt):
            write_payload(payload, fmt=fmt)
        else:
            write_text(_render_text(payload))
        return 0


class _FindQuery:
    def __init__(
        self,
        *,
        connect_hosts: tuple[str, ...],
        kafka_bootstrap: tuple[str, ...],
        schema_registry_urls: tuple[str, ...],
        connectors: tuple[str, ...],
    ) -> None:
        self.connect_hosts = connect_hosts
        self.kafka_bootstrap = kafka_bootstrap
        self.schema_registry_urls = schema_registry_urls
        self.connectors = connectors

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "_FindQuery":
        return cls(
            connect_hosts=tuple(
                split_repeatable_csv(getattr(args, "connect_host", None))
            ),
            kafka_bootstrap=tuple(
                split_repeatable_csv(getattr(args, "kafka_bootstrap", None))
            ),
            schema_registry_urls=tuple(
                split_repeatable_csv(getattr(args, "schema_registry_url", None))
            ),
            connectors=tuple(split_repeatable_csv(getattr(args, "connector", None))),
        )

    @property
    def is_empty(self) -> bool:
        return not (
            self.connect_hosts
            or self.kafka_bootstrap
            or self.schema_registry_urls
            or self.connectors
        )

    def to_payload(self) -> dict[str, list[str]]:
        return {
            "connect_hosts": list(self.connect_hosts),
            "kafka_bootstrap": list(self.kafka_bootstrap),
            "schema_registry_urls": list(self.schema_registry_urls),
            "connectors": list(self.connectors),
        }


def _matched_by(query: _FindQuery, env: ConfigClusterEnvInventory) -> list[str]:
    matched: list[str] = []
    if query.connect_hosts and all(
        endpoint_matches(item, env.connect_hosts)
        or endpoint_matches(item, env.connect_urls)
        for item in query.connect_hosts
    ):
        matched.append("connect-host")
    if query.kafka_bootstrap and all(
        endpoint_matches(item, env.kafka_bootstrap_servers)
        or endpoint_matches(item, env.kafka_hosts)
        for item in query.kafka_bootstrap
    ):
        matched.append("kafka-bootstrap")
    if query.schema_registry_urls and all(
        endpoint_matches(item, env.schema_registry_urls)
        for item in query.schema_registry_urls
    ):
        matched.append("schema-registry")
    # Connector-level filtering is intentionally routed through bkkt search in
    # the text hints for now; config find stays a pure connectctl inventory lookup.
    if query.connectors:
        matched.append("connector-filter-not-evaluated")
    expected_groups = sum(
        bool(group)
        for group in (
            query.connect_hosts,
            query.kafka_bootstrap,
            query.schema_registry_urls,
            query.connectors,
        )
    )
    return matched if len(matched) == expected_groups else []


def _render_text(payload: Dict[str, Any]) -> str:
    rows: List[Dict[str, str]] = []
    for match in payload["matches"]:
        rows.append(
            {
                "cluster": match["cluster_group"],
                "env": match["env"],
                "matched_by": ", ".join(match["matched_by"]),
                "connect": "\n".join(match["connect_hosts"]) or "-",
                "kafka": "\n".join(match["kafka_bootstrap_servers"]) or "-",
                "schema_registry": "\n".join(match["schema_registry_urls"]) or "-",
            }
        )
    lines = [
        "# BKKT: config find\n",
        f"- matches: `{payload['match_count']}`\n",
        render_terminal_table(
            (
                TableColumn("cluster", "Cluster group", max_width=36),
                TableColumn("env", "Env", max_width=5),
                TableColumn("matched_by", "Matched by", max_width=28),
                TableColumn("connect", "Connect hosts", max_width=28),
                TableColumn("kafka", "Kafka bootstrap", max_width=36),
                TableColumn("schema_registry", "Schema Registry", max_width=36),
            ),
            rows,
        ),
        "\n## Next commands\n",
        "- `bkkt config clusters --view details`\n",
        "- `bkkt search --config-eq KEY=VALUE --source repo`\n",
    ]
    return "\n".join(lines) + "\n"


__all__ = ["ConfigFindService"]
