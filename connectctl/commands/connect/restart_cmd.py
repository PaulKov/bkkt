from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from ...cli_helpers.clusters_arg import parse_clusters_selection
from ...cli_helpers.concurrency_args import add_concurrency_args
from ...cli_helpers.default_scope_ux import (
    confirm_broad_scope,
    effective_value,
    log_effective_values,
)
from ...cli_helpers.live_scopes import LiveScope, dedupe_live_scopes
from ...cli_helpers.output_args import add_output_format_args
from ...exceptions import ConfigError
from ...execution import ConcurrencyOptions, RateLimiter, map_collect, map_fail_fast
from ...logging_utils import get_logger
from ...output import is_machine_output, resolve_output_format, write_payload
from ...services.connect_ops import is_all_cluster_token
from .common import (
    add_selector_args,
    add_runtime_break_glass_arg,
    add_target_args,
    has_any_selector,
    resolve_target,
    select_connectors,
)


@dataclass(frozen=True)
class RestartScopeResult:
    cluster_scope: str
    aliases: tuple[dict[str, object], ...]
    selected: tuple[str, ...]
    restart_candidates: tuple[str, ...]
    restarted: int
    skipped: int
    dry_run: bool


def cmd_connect_restart(args: argparse.Namespace, *, ctx, logger=None) -> int:
    """Рестарт коннекторов с single-cluster и bulk recovery режимами."""

    log = get_logger(logger or getattr(ctx, "logger", None))

    conc = ConcurrencyOptions.from_args(args)
    throttle = (
        RateLimiter(conc.rate_limit_per_second, burst=conc.burst)
        if conc.rate_limit_per_second > 0
        else None
    )
    scope = _normalize_scope(args)

    log_effective_values(
        log,
        command="connect restart",
        values=(
            effective_value(args, "env", getattr(args, "env", None)),
            effective_value(args, "cluster", getattr(args, "cluster", None) or "-"),
            effective_value(
                args,
                "clusters",
                _render_clusters_value(getattr(args, "clusters", None)),
            ),
            effective_value(args, "scope", scope),
            effective_value(args, "jobs", getattr(args, "jobs", None)),
        ),
    )

    if is_all_cluster_token(getattr(args, "cluster", None)):
        if getattr(args, "clusters", None) is not None:
            raise ConfigError(
                "Нельзя использовать одновременно --cluster all и --clusters"
            )
        args.clusters = "all"
        args.cluster = None

    if getattr(args, "cluster", None) and getattr(args, "clusters", None) is not None:
        raise ConfigError(
            "Нельзя использовать одновременно --cluster (single target) и --clusters (bulk filter)"
        )

    if getattr(args, "clusters", None) is None:
        return _run_single_cluster(
            args=args,
            ctx=ctx,
            log=log,
            conc=conc,
            throttle=throttle,
            scope=scope,
        )

    return _run_bulk_clusters(
        args=args,
        ctx=ctx,
        log=log,
        conc=conc,
        throttle=throttle,
        scope=scope,
    )


def _run_single_cluster(*, args, ctx, log, conc, throttle, scope: str) -> int:
    target = resolve_target(ctx, args, throttle=throttle, logger=log)

    selected, _missing = select_connectors(
        connect=target.client,
        args=args,
        default_all=False,
    )

    if not has_any_selector(args):
        if scope in {"failed", "failed-tasks"}:
            selected = list(target.client.list_connectors())
            log.info(
                "Restart recovery mode: selector omitted, implicitly using --all for scope=%s",
                scope,
            )
            if not confirm_broad_scope(
                args,
                prompt=(
                    f"Продолжить restart recovery для всех коннекторов в {target.cluster.name}/{target.env.value}?"
                ),
                logger=log,
            ):
                return 1
        else:
            raise ConfigError(
                "Restart требует селектор: используйте --all, --names a,b,c или --regexp <re>"
            )

    dry_run = bool(getattr(args, "dry_run", False))
    if not dry_run:
        ctx.assert_rest_mutation_allowed(
            target.env,
            target.cluster.name,
            command="connect restart",
            unsafe=bool(getattr(args, "runtime_unsafe_rest", False)),
        )

    result = _restart_scope(
        connect=target.client,
        selected=selected,
        scope=scope,
        conc=conc,
        dry_run=dry_run,
        aliases=(
            {
                "cluster": target.cluster.name,
                "env": target.env.value,
                "urls": list(target.cluster.urls),
            },
        ),
    )
    payload = _build_restart_payload(
        env=target.env.value,
        scope=scope,
        dry_run=bool(getattr(args, "dry_run", False)),
        results=[result],
        deduped_targets=1,
    )
    _emit_restart_summary(args, payload)
    return 0


def _run_bulk_clusters(*, args, ctx, log, conc, throttle, scope: str) -> int:
    env = ctx.env(getattr(args, "env"))
    selected_clusters = parse_clusters_selection(
        getattr(args, "clusters", None),
        available=ctx.settings.cluster_groups.keys(),
        allow_all_keyword=True,
    )
    if selected_clusters is None or not selected_clusters:
        raise ConfigError(
            "--clusters пустой; укажите имена через запятую или используйте --clusters all"
        )

    scopes = dedupe_live_scopes(
        settings=ctx.settings,
        envs=(env.value,),
        cluster_groups=selected_clusters,
    )
    if not scopes:
        log.info("No live targets for env=%s clusters=%s", env.value, selected_clusters)
        _emit_restart_summary(
            args,
            _build_restart_payload(
                env=env.value,
                scope=scope,
                dry_run=bool(getattr(args, "dry_run", False)),
                results=[],
                deduped_targets=0,
            ),
        )
        return 0

    if _requires_bulk_restart_confirmation(args, scopes=scopes, scope=scope):
        if not confirm_broad_scope(
            args,
            prompt=(
                "Продолжить bulk restart recovery "
                f"для env={env.value} clusters={','.join(selected_clusters)} scope={scope}?"
            ),
            logger=log,
        ):
            return 1

    results: List[RestartScopeResult] = []
    for live_scope in scopes:
        target = ctx.connect_target(
            live_scope.primary_env,
            live_scope.primary_cluster,
            throttle=throttle,
        )
        ctx.print_cluster_banner(target)
        selected = _select_scope_connectors(
            args=args,
            connect=target.client,
            scope=scope,
            log=log,
            cluster_scope=_scope_label(live_scope),
        )
        if not selected:
            results.append(
                RestartScopeResult(
                    cluster_scope=_scope_label(live_scope),
                    aliases=_scope_aliases(live_scope),
                    selected=(),
                    restart_candidates=(),
                    restarted=0,
                    skipped=0,
                    dry_run=bool(getattr(args, "dry_run", False)),
                )
            )
            continue
        dry_run = bool(getattr(args, "dry_run", False))
        if not dry_run:
            ctx.assert_rest_mutation_allowed(
                live_scope.primary_env,
                live_scope.primary_cluster,
                command="connect restart",
                unsafe=bool(getattr(args, "runtime_unsafe_rest", False)),
            )
        results.append(
            _restart_scope(
                connect=target.client,
                selected=selected,
                scope=scope,
                conc=conc,
                dry_run=dry_run,
                aliases=_scope_aliases(live_scope),
                cluster_scope=_scope_label(live_scope),
            )
        )

    payload = _build_restart_payload(
        env=env.value,
        scope=scope,
        dry_run=bool(getattr(args, "dry_run", False)),
        results=results,
        deduped_targets=len(scopes),
    )
    _emit_restart_summary(args, payload)
    return 0


def _restart_scope(
    *,
    connect,
    selected: Sequence[str],
    scope: str,
    conc,
    dry_run: bool,
    aliases: Sequence[dict[str, object]],
    cluster_scope: str | None = None,
) -> RestartScopeResult:
    to_restart = _filter_restart_candidates(
        connect=connect,
        selected=selected,
        scope=scope,
        conc=conc,
    )

    include_tasks = scope != "failed"
    only_failed = scope != "all"

    def _restart_one(name: str) -> tuple[int, int]:
        if dry_run:
            return (0, 1)
        connect.restart(name, include_tasks=include_tasks, only_failed=only_failed)
        return (1, 0)

    if conc.jobs <= 1:
        execution = [_restart_one(name) for name in to_restart]
    else:
        execution = map_fail_fast(to_restart, _restart_one, jobs=conc.jobs)

    restarted = sum(item[0] for item in execution)
    skipped = sum(item[1] for item in execution)
    return RestartScopeResult(
        cluster_scope=cluster_scope or _aliases_label(aliases),
        aliases=tuple(aliases),
        selected=tuple(selected),
        restart_candidates=tuple(to_restart),
        restarted=restarted,
        skipped=skipped,
        dry_run=dry_run,
    )


def _filter_restart_candidates(
    *, connect, selected: Sequence[str], scope: str, conc
) -> list[str]:
    if scope == "all":
        return list(selected)

    def _needs_restart(name: str) -> bool:
        try:
            status = connect.get_status(name)
        except Exception:
            return True
        if scope == "failed":
            return status.connector_state.upper() == "FAILED"
        return status.connector_state.upper() == "FAILED" or any(
            item.upper() == "FAILED" for item in status.task_states
        )

    if conc.jobs <= 1:
        return [name for name in selected if _needs_restart(name)]

    return [
        result.item
        for result in map_collect(selected, _needs_restart, jobs=conc.jobs)
        if result.error is not None or bool(result.value)
    ]


def _select_scope_connectors(
    *, args, connect, scope: str, log, cluster_scope: str
) -> list[str]:
    selected, _missing = select_connectors(
        connect=connect,
        args=args,
        default_all=False,
    )
    if has_any_selector(args):
        return selected
    if scope == "all":
        raise ConfigError(
            "Restart требует селектор: используйте --all, --names a,b,c или --regexp <re>"
        )
    log.info(
        "Restart recovery mode for %s: selector omitted, implicitly using --all",
        cluster_scope,
    )
    return list(connect.list_connectors())


def _normalize_scope(args) -> str:
    scope = str(getattr(args, "scope", "failed-tasks")).strip().lower()
    if scope not in {"failed", "failed-tasks", "all"}:
        raise ConfigError("Некорректный --scope. Ожидается: failed, failed-tasks, all")
    return scope


def _requires_bulk_restart_confirmation(
    args, *, scopes: Sequence[LiveScope], scope: str
) -> bool:
    if scope == "all":
        return True
    if not has_any_selector(args):
        return True
    return len(scopes) > 1


def _render_clusters_value(raw: object) -> str:
    if raw is None:
        return "-"
    if raw == "":
        return "-"
    return str(raw)


def _scope_aliases(scope: LiveScope) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "cluster": alias.cluster,
            "env": alias.env,
            "urls": list(alias.urls),
        }
        for alias in scope.aliases
    )


def _scope_label(scope: LiveScope) -> str:
    aliases = ",".join(f"{alias.cluster}/{alias.env}" for alias in scope.aliases)
    return f"{aliases} urls=[{', '.join(scope.urls)}]"


def _aliases_label(aliases: Sequence[dict[str, object]]) -> str:
    return ",".join(f"{item['cluster']}/{item['env']}" for item in aliases)


def _build_restart_payload(
    *,
    env: str,
    scope: str,
    dry_run: bool,
    results: Sequence[RestartScopeResult],
    deduped_targets: int,
) -> Dict[str, Any]:
    total_selected = sum(len(item.selected) for item in results)
    total_candidates = sum(len(item.restart_candidates) for item in results)
    total_restarted = sum(item.restarted for item in results)
    total_skipped = sum(item.skipped for item in results)
    return {
        "command": "connect restart",
        "env": env,
        "scope": scope,
        "dry_run": dry_run,
        "deduped_targets": deduped_targets,
        "counts": {
            "selected": total_selected,
            "restart_candidates": total_candidates,
            "restarted": total_restarted,
            "skipped": total_skipped,
        },
        "targets": [
            {
                "cluster_scope": item.cluster_scope,
                "aliases": list(item.aliases),
                "selected": list(item.selected),
                "restart_candidates": list(item.restart_candidates),
                "restarted": item.restarted,
                "skipped": item.skipped,
                "dry_run": item.dry_run,
            }
            for item in results
        ],
    }


def _emit_restart_summary(args, payload: Dict[str, Any]) -> None:
    log = get_logger(None)
    log.info(
        "Restart summary: targets=%s selected=%s candidates=%s restarted=%s skipped=%s",
        payload["deduped_targets"],
        payload["counts"]["selected"],
        payload["counts"]["restart_candidates"],
        payload["counts"]["restarted"],
        payload["counts"]["skipped"],
    )
    fmt = resolve_output_format(args)
    if is_machine_output(fmt):
        write_payload(payload, fmt=fmt)


def register_parser(connect_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    s = connect_sub.add_parser("restart", help="Перезапуск коннекторов")
    add_target_args(s)
    s.add_argument(
        "--clusters",
        nargs="?",
        const="all",
        default=None,
        help=(
            "Bulk recovery по набору cluster groups без override. "
            "Укажите список через запятую или используйте --clusters all. "
            "Нельзя использовать вместе с --cluster."
        ),
    )
    add_selector_args(s, default_all=False)
    add_concurrency_args(s)
    add_runtime_break_glass_arg(s)
    add_output_format_args(s)
    s.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Не спрашивать подтверждение для широкого restart recovery",
    )
    s.add_argument(
        "--scope",
        choices=["failed", "failed-tasks", "all"],
        default="failed-tasks",
        help="failed=только FAILED connector, failed-tasks=FAILED connector или tasks, all=все",
    )
    s.add_argument(
        "--dry-run", action="store_true", help="Ничего не делать, только показать план"
    )
    s.set_defaults(func=cmd_connect_restart)
    return s
