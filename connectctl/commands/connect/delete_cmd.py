from __future__ import annotations

import argparse
import sys

from ...cli_helpers.concurrency_args import add_concurrency_args
from ...cli_helpers.side_effect_preview import log_action_plan, log_action_summary
from ...exceptions import ConfigError
from ...execution import ConcurrencyOptions, RateLimiter, map_fail_fast
from ...logging_utils import get_logger
from ...services.connect_delete_safety import (
    DeleteSafetyInspector,
    enforce_safe_delete,
)
from .common import (
    add_yes_arg,
    add_selector_args,
    add_runtime_break_glass_arg,
    add_target_args,
    enforce_fanout_mutation_policy,
    enforce_runtime_mutation_guard_for_target,
    has_any_selector,
    resolve_target_plan,
    select_connectors,
)


def cmd_connect_delete(args: argparse.Namespace, *, ctx, logger=None) -> int:
    """Удаление коннекторов с подтверждением (если не -y)."""

    log = get_logger(logger or getattr(ctx, "logger", None))

    conc = ConcurrencyOptions.from_args(args)
    throttle = (
        RateLimiter(conc.rate_limit_per_second, burst=conc.burst)
        if conc.rate_limit_per_second > 0
        else None
    )

    if not has_any_selector(args):
        raise ConfigError(
            "Delete требует селектор: используйте --all, --names a,b,c или --regexp <re>"
        )

    dry_run = bool(getattr(args, "dry_run", False))
    assume_yes = bool(getattr(args, "yes", False))
    unsafe = bool(getattr(args, "unsafe", False))

    plan = resolve_target_plan(ctx, args, throttle=throttle, logger=log)
    enforce_fanout_mutation_policy(
        args=args, plan=plan, command="connect delete", dry_run=dry_run
    )

    selected_by_target = []
    for execution_target in plan.targets:
        target = execution_target.target
        selected, missing = select_connectors(
            connect=target.client,
            args=args,
            default_all=False,
        )
        if missing:
            raise ConfigError(f"Коннектор(ы) не найдены: {', '.join(missing)}")

        log_action_plan(
            log,
            action=f"DELETE {target.cluster.name}/{target.env.value}",
            targets=selected,
            dry_run=dry_run,
        )

        if unsafe:
            log.warning(
                "UNSAFE delete mode enabled: pre-delete checks are skipped; DELETE will be sent directly."
            )
        else:
            inspector = DeleteSafetyInspector(
                connect=target.client,
                kafka=getattr(target.cluster, "kafka", None),
            )
            for name in selected:
                report = inspector.inspect(name)
                for check in report.checks:
                    level = log.warning if check.status == "warn" else log.info
                    if check.status == "fail":
                        level = log.error
                    level(
                        "safe-delete %s/%s %s: %s=%s (%s)",
                        target.cluster.name,
                        target.env.value,
                        name,
                        check.name,
                        check.status,
                        check.detail,
                    )
                enforce_safe_delete(report)
        selected_by_target.append((target, list(selected)))

    if dry_run:
        log.info("[DRY-RUN] Удаление не выполнялось.")
        log_action_summary(
            log,
            action="DELETE",
            done=0,
            skipped=sum(len(item[1]) for item in selected_by_target),
        )
        return 0

    if not assume_yes:
        if not sys.stdin.isatty():
            raise ConfigError(
                "Отказ: нельзя удалять без -y/--yes в неинтерактивном режиме"
            )
        ans = input("Продолжить удаление? [y/N]: ").strip().lower()
        if ans not in {"y", "yes"}:
            log.warning("Отменено.")
            return 1

    done = 0
    for target, selected in selected_by_target:
        enforce_runtime_mutation_guard_for_target(
            ctx, args, target, command="connect delete", dry_run=dry_run
        )

        def _delete_one(name: str) -> None:
            target.client.delete(name)
            log.info("deleted: %s", name)

        if conc.jobs <= 1:
            for name in selected:
                _delete_one(name)
        else:
            map_fail_fast(selected, _delete_one, jobs=conc.jobs)
        done += len(selected)

    log_action_summary(log, action="DELETE", done=done, skipped=0)
    return 0


def register_parser(connect_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    s = connect_sub.add_parser("delete", help="Удаление коннекторов")
    add_target_args(s)
    add_selector_args(s, default_all=False)
    add_concurrency_args(s)
    add_runtime_break_glass_arg(s)
    add_yes_arg(s, help_text="Не спрашивать подтверждение")
    s.add_argument(
        "--unsafe",
        action="store_true",
        help=(
            "Отключить safe pre-delete checks и сразу отправить DELETE. "
            "По умолчанию delete работает в safe mode."
        ),
    )
    s.add_argument(
        "--dry-run", action="store_true", help="Ничего не делать, только показать план"
    )
    s.set_defaults(func=cmd_connect_delete)
    return s
