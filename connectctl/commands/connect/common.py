from __future__ import annotations

import argparse
from typing import List, Tuple

from ...cli_support import _print_cluster_banner, _select_connectors
from ...ports import ConnectApi
from ...logging_utils import get_logger
from ...models import Environment
from ...app.context import CliContext, ConnectTarget
from ...services.connect_ops import (
    ConnectExecutionPlan,
    ConnectMutationSafetyPolicy,
    ConnectTargetExecutor,
)


def add_target_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--env", required=True, help="Целевое окружение (dev|stage|prod)")
    p.add_argument(
        "--cluster",
        default=None,
        help=(
            "Имя группы кластеров (cluster group), либо all/* для fan-out. "
            "По умолчанию: default_cluster из connectctl.yaml"
        ),
    )


def add_yes_arg(p: argparse.ArgumentParser, *, help_text: str | None = None) -> None:
    p.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=help_text or "Не спрашивать подтверждение для mutating операций",
    )


def add_runtime_break_glass_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--runtime-unsafe-rest",
        action="store_true",
        help=(
            "Break-glass: allow raw Kafka Connect REST mutations for operator-managed "
            "runtimes (Strimzi/CFK). Prefer CRD/GitOps mutation instead."
        ),
    )


def add_selector_args(p: argparse.ArgumentParser, *, default_all: bool) -> None:
    p.add_argument("--names", default=None, help="Имена коннекторов через запятую")
    p.add_argument(
        "--regexp",
        action="append",
        default=[],
        help="Регулярное выражение для фильтрации имён (можно указывать несколько раз)",
    )
    if default_all:
        p.add_argument(
            "--all",
            action="store_true",
            help="Использовать все коннекторы (по умолчанию, если не указаны --names/--regexp)",
        )
    else:
        p.add_argument(
            "--all",
            action="store_true",
            help="Использовать все коннекторы (обязательно, если не указаны --names/--regexp)",
        )


def has_any_selector(args: argparse.Namespace) -> bool:
    return (
        bool(getattr(args, "all", False))
        or bool(getattr(args, "names", None))
        or bool(getattr(args, "regexp", None))
    )


def resolve_target(
    ctx: CliContext, args: argparse.Namespace, *, throttle=None, logger=None
) -> ConnectTarget:
    """Resolve Connect target (env + cluster group) and create a ConnectApi."""

    log = get_logger(logger or ctx.logger)

    env = Environment.from_str(str(getattr(args, "env")).strip().lower())
    cluster = ctx.resolve_cluster(env, getattr(args, "cluster", None))
    client = ctx.connect_client(env, getattr(args, "cluster", None), throttle=throttle)
    target = ConnectTarget(env=env, cluster=cluster, client=client)

    # Banner once per command.
    _print_cluster_banner(cluster, env, logger=log)

    return target


def resolve_target_plan(
    ctx: CliContext,
    args: argparse.Namespace,
    *,
    throttle=None,
    timeout=None,
    logger=None,
    print_banners: bool = True,
) -> ConnectExecutionPlan:
    return ConnectTargetExecutor(ctx=ctx, logger=logger or ctx.logger).resolve_plan(
        env_arg=str(getattr(args, "env")),
        cluster_arg=getattr(args, "cluster", None),
        throttle=throttle,
        timeout=timeout,
        print_banners=print_banners,
    )


def enforce_fanout_mutation_policy(
    *,
    args: argparse.Namespace,
    plan: ConnectExecutionPlan,
    command: str,
    dry_run: bool,
) -> None:
    ConnectMutationSafetyPolicy(command=command).require_allowed(
        is_fanout=plan.is_fanout,
        has_selector=has_any_selector(args),
        dry_run=dry_run,
        assume_yes=bool(getattr(args, "yes", False)),
    )


def enforce_runtime_mutation_guard(
    ctx: CliContext,
    args: argparse.Namespace,
    *,
    command: str,
    dry_run: bool,
) -> None:
    if dry_run:
        return
    env = Environment.from_str(str(getattr(args, "env")).strip().lower())
    guard = getattr(ctx, "assert_rest_mutation_allowed", None)
    if callable(guard):
        guard(
            env,
            getattr(args, "cluster", None),
            command=command,
            unsafe=bool(getattr(args, "runtime_unsafe_rest", False)),
        )


def enforce_runtime_mutation_guard_for_target(
    ctx: CliContext,
    args: argparse.Namespace,
    target: ConnectTarget,
    *,
    command: str,
    dry_run: bool,
) -> None:
    if dry_run:
        return
    guard = getattr(ctx, "assert_rest_mutation_allowed", None)
    if callable(guard):
        guard(
            target.env,
            target.cluster.name,
            command=command,
            unsafe=bool(getattr(args, "runtime_unsafe_rest", False)),
        )


def select_connectors(
    *,
    connect: ConnectApi,
    args: argparse.Namespace,
    default_all: bool,
) -> Tuple[List[str], List[str]]:
    """Select connectors from a cluster based on --names/--regexp/--all."""

    names_csv = getattr(args, "names", None)
    regexps = getattr(args, "regexp", None)
    all_flag = bool(getattr(args, "all", False))

    if default_all and not all_flag and not names_csv and not (regexps or []):
        all_flag = True

    selected, missing = _select_connectors(
        connect=connect,
        names_csv=names_csv,
        regexps=list(regexps or []),
        all_flag=all_flag,
    )
    return selected, missing


def build_target_routing_payload(target: ConnectTarget) -> dict[str, object]:
    return {
        "cluster": {
            "group": target.cluster.name,
            "env": target.env.value,
            "urls": list(target.cluster.urls),
        },
        "source": "cli",
        "target": f"{target.cluster.name}/{target.env.value}",
    }
