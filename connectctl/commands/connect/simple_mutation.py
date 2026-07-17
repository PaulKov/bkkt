from __future__ import annotations

import argparse
from typing import Callable

from ...cli_helpers.side_effect_preview import log_action_plan, log_action_summary
from ...exceptions import ConfigError
from ...execution import ConcurrencyOptions, RateLimiter, map_fail_fast
from ...logging_utils import get_logger
from ...ports import ConnectApi
from .common import (
    enforce_fanout_mutation_policy,
    enforce_runtime_mutation_guard_for_target,
    has_any_selector,
    resolve_target_plan,
    select_connectors,
)


ConnectAction = Callable[[ConnectApi, str], None]


def run_simple_connector_mutation(
    *,
    args: argparse.Namespace,
    ctx,
    logger,
    action_label: str,
    command: str,
    empty_message: str,
    dry_run_message: str,
    done_message: str,
    operation: ConnectAction,
) -> int:
    """Run a connector-level mutation across one or more Connect targets."""

    log = get_logger(logger or getattr(ctx, "logger", None))

    if not has_any_selector(args):
        raise ConfigError(
            f"{action_label.lower()} требует селектор: используйте --all, --names a,b,c или --regexp <re>"
        )

    conc = ConcurrencyOptions.from_args(args)
    throttle = (
        RateLimiter(conc.rate_limit_per_second, burst=conc.burst)
        if conc.rate_limit_per_second > 0
        else None
    )
    dry_run = bool(getattr(args, "dry_run", False))
    plan = resolve_target_plan(ctx, args, throttle=throttle, logger=log)
    enforce_fanout_mutation_policy(
        args=args,
        plan=plan,
        command=command,
        dry_run=dry_run,
    )

    done_total = 0
    skipped_total = 0
    for execution_target in plan.targets:
        target = execution_target.target
        selected, missing = select_connectors(
            connect=target.client, args=args, default_all=False
        )
        if missing:
            raise ConfigError(f"Коннектор(ы) не найдены: {', '.join(missing)}")

        names = list(selected)
        if not names:
            log.info("%s", empty_message)
            continue

        log_action_plan(
            log,
            action=f"{action_label} {target.cluster.name}/{target.env.value}",
            targets=names,
            dry_run=dry_run,
        )
        enforce_runtime_mutation_guard_for_target(
            ctx, args, target, command=command, dry_run=dry_run
        )

        def _run_one(name: str) -> tuple[int, int]:
            if dry_run:
                log.info(dry_run_message, name)
                return (0, 1)
            operation(target.client, name)
            log.info(done_message, name)
            return (1, 0)

        if conc.jobs <= 1:
            results = [_run_one(name) for name in names]
        else:
            results = map_fail_fast(names, _run_one, jobs=conc.jobs)

        done_total += sum(item[0] for item in results)
        skipped_total += sum(item[1] for item in results)

    log_action_summary(log, action=action_label, done=done_total, skipped=skipped_total)
    return 0


__all__ = ["run_simple_connector_mutation"]
