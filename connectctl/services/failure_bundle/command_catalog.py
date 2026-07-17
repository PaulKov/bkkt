from __future__ import annotations

from dataclasses import dataclass

from .models import FailureAnalysisContext
from .utils import command, dedupe_keep_order


@dataclass(frozen=True)
class FailureCommandCatalog:
    inspect: str | None = None
    inspect_vars: str | None = None
    render: str | None = None
    validate: str | None = None
    compare: str | None = None
    validate_connect: str | None = None
    apply_dry_run: str | None = None
    get_connector: str | None = None
    connectors: str | None = None
    connect_status: str | None = None
    connect_endpoints: str | None = None
    connect_status_watch: str | None = None
    connect_update_dry_run: str | None = None
    connect_create_dry_run: str | None = None
    connect_patch_dry_run: str | None = None
    restart_failed_tasks: str | None = None
    restart_failed_tasks_bulk: str | None = None

    @classmethod
    def from_context(cls, context: FailureAnalysisContext) -> "FailureCommandCatalog":
        cluster_flag = (
            ("--cluster", context.cluster_group) if context.cluster_group else ()
        )
        selector_tokens = context.selector_tokens or (
            ("--names", context.name) if context.name else ()
        )

        return cls(
            inspect=(
                command("bkkt", "inspect", context.path, "--output", "json")
                if context.path
                else None
            ),
            inspect_vars=(
                command("bkkt", "inspect", context.path, "--explain-vars")
                if context.path
                else None
            ),
            render=command("bkkt", "render", context.path) if context.path else None,
            validate=(
                command("bkkt", "validate", context.path) if context.path else None
            ),
            compare=(
                command("bkkt", "compare", context.path, *cluster_flag)
                if context.path
                else None
            ),
            validate_connect=(
                command(
                    "bkkt",
                    "validate-connect",
                    "--env",
                    context.env,
                    *cluster_flag,
                    context.path,
                )
                if context.path
                else None
            ),
            apply_dry_run=(
                command(
                    "bkkt",
                    "apply",
                    "--env",
                    context.env,
                    *cluster_flag,
                    "--dry-run",
                    context.path,
                )
                if context.path and context.command == "apply"
                else None
            ),
            get_connector=(
                command(
                    "bkkt",
                    "get-connector",
                    "--env",
                    context.env,
                    *cluster_flag,
                    "--status",
                    "long",
                    context.name,
                )
                if context.name
                else None
            ),
            connectors=command(
                "bkkt",
                "connect",
                "status",
                "--env",
                context.env,
                *cluster_flag,
                "--status",
                "short",
            ),
            connect_status=(
                command(
                    "bkkt",
                    "connect",
                    "status",
                    "--env",
                    context.env,
                    *cluster_flag,
                    *selector_tokens,
                    "--status",
                    "short",
                )
                if selector_tokens
                else None
            ),
            connect_endpoints=command(
                "bkkt",
                "connect",
                "endpoints",
                "--env",
                context.env,
                *cluster_flag,
                *(("--name", context.name) if context.name else ()),
            ),
            connect_status_watch=(
                command(
                    "bkkt",
                    "connect",
                    "status",
                    "--env",
                    context.env,
                    *cluster_flag,
                    *selector_tokens,
                    "--watch",
                    "--until-healthy",
                    "--interval-seconds",
                    "2",
                )
                if selector_tokens
                else None
            ),
            connect_update_dry_run=(
                command(
                    "bkkt",
                    "connect",
                    "update",
                    "--env",
                    context.env,
                    *cluster_flag,
                    "--name",
                    context.name,
                    context.input_src,
                    "--dry-run",
                    "--diff",
                )
                if context.command == "connect-create"
                and context.name
                and context.input_src
                and context.input_src != "-"
                else None
            ),
            connect_create_dry_run=(
                command(
                    "bkkt",
                    "connect",
                    "create",
                    "--env",
                    context.env,
                    *cluster_flag,
                    "--name",
                    context.name,
                    "--dry-run",
                    context.input_src,
                )
                if context.command in {"connect-update", "connect-patch"}
                and context.name
                and context.input_src
                and context.input_src != "-"
                else None
            ),
            connect_patch_dry_run=(
                command(
                    "bkkt",
                    "connect",
                    "patch",
                    "--env",
                    context.env,
                    *cluster_flag,
                    "--names",
                    context.name,
                    "--set",
                    "key=value",
                    "--dry-run",
                    "--diff",
                )
                if context.name
                else None
            ),
            restart_failed_tasks=(
                command(
                    "bkkt",
                    "connect",
                    "restart",
                    "--env",
                    context.env,
                    *cluster_flag,
                    "--names",
                    context.name,
                    "--scope",
                    "failed-tasks",
                    "--dry-run",
                )
                if context.name and context.cluster_group
                else None
            ),
            restart_failed_tasks_bulk=(
                command(
                    "bkkt",
                    "connect",
                    "restart",
                    "--env",
                    context.env,
                    "--clusters",
                    context.cluster_group,
                    "--scope",
                    "failed-tasks",
                    "--dry-run",
                )
                if context.cluster_group
                else None
            ),
        )

    def select(self, *names: str) -> tuple[str, ...]:
        return tuple(
            dedupe_keep_order(
                [
                    value
                    for name in names
                    for value in [getattr(self, name)]
                    if value is not None
                ]
            )
        )
