from __future__ import annotations

import argparse
from typing import Sequence

from ...cli_support import _read_patch_payload, _split_patch_set_and_delete
from ...cli_helpers.audit_args import add_audit_args
from ...cli_helpers.concurrency_args import add_concurrency_args
from ...cli_helpers.failure_bundle_args import add_failure_bundle_dir_arg
from ...cli_helpers.side_effect_preview import log_action_plan, log_action_summary
from ...diffing import (
    config_key_changes,
    config_unified_diff,
    configs_equal,
    format_config_key_changes,
    summarize_diff,
)
from ...exceptions import ConfigError
from ...execution import ConcurrencyOptions, RateLimiter, map_fail_fast
from ...logging_utils import get_logger
from ...services.failure_bundle import FailureBundleWriter
from ...services.audit import audit_session_from_args
from .common import (
    add_yes_arg,
    add_selector_args,
    add_runtime_break_glass_arg,
    add_target_args,
    build_target_routing_payload,
    enforce_fanout_mutation_policy,
    enforce_runtime_mutation_guard_for_target,
    has_any_selector,
    resolve_target_plan,
    select_connectors,
)


def cmd_connect_patch(args: argparse.Namespace, *, ctx, logger=None) -> int:
    """Частичное обновление (patch) конфига коннектора: GET+merge+PUT.

    Kafka Connect не предоставляет нативного PATCH endpoint, поэтому реализовано как:
      1) GET /connectors/<name>/config
      2) применяем patch (set/delete)
      3) PUT /connectors/<name>/config
    """

    log = get_logger(logger or getattr(ctx, "logger", None))
    writer = FailureBundleWriter.from_args(
        command="connect-patch",
        repo_root=ctx.repo_root,
        fs=ctx.fs,
        args=args,
    )

    conc = ConcurrencyOptions.from_args(args)
    throttle = (
        RateLimiter(conc.rate_limit_per_second, burst=conc.burst)
        if conc.rate_limit_per_second > 0
        else None
    )

    stage = "resolve_target"
    target = None
    selected: list[str] = []
    patch_set: dict[str, str] = {}
    patch_delete: Sequence[str] = ()
    current_name: str | None = None
    current_desired: dict[str, object] | None = None
    try:
        with audit_session_from_args(
            command="connect patch", args=args, ctx=ctx
        ) as audit:
            if not has_any_selector(args):
                raise ConfigError(
                    "Patch требует селектор: используйте --all, --names a,b,c или --regexp <re>"
                )

            stage = "resolve_targets"
            plan = resolve_target_plan(ctx, args, throttle=throttle, logger=log)

            stage = "read_payload"
            patch_raw = _read_patch_payload(args)
            patch_set, patch_delete = _split_patch_set_and_delete(patch_raw)
            audit.event(
                "patch_payload_prepared",
                payload={
                    "set_keys": sorted(patch_set.keys()),
                    "delete_keys": sorted(str(key) for key in patch_delete),
                },
            )

            dry_run = bool(getattr(args, "dry_run", False))
            enforce_fanout_mutation_policy(
                args=args, plan=plan, command="connect patch", dry_run=dry_run
            )
            show_structured_diff = bool(getattr(args, "diff", False))
            diff_max_keys = int(getattr(args, "diff_max_keys", 50) or 50)
            skip_if_no_change = bool(getattr(args, "skip_if_no_change", True))

            set_keys = sorted(patch_set.keys())
            del_keys = sorted(set(patch_delete))

            if set_keys:
                if len(set_keys) <= 20:
                    log.info("Patch set: " + ", ".join(set_keys))
                else:
                    log.info(
                        "Patch set: "
                        + ", ".join(set_keys[:20])
                        + f" … (+{len(set_keys) - 20} more)"
                    )
            if del_keys:
                if len(del_keys) <= 20:
                    log.info("Patch delete: " + ", ".join(del_keys))
                else:
                    log.info(
                        "Patch delete: "
                        + ", ".join(del_keys[:20])
                        + f" … (+{len(del_keys) - 20} more)"
                    )

            updated_total = 0
            skipped_total = 0

            def _patch_one(target_obj, name: str) -> tuple[int, int]:
                nonlocal current_name, current_desired, stage
                current_name = name
                stage = "fetch_config"
                existing = target_obj.client.get_config_optional(name)
                if existing is None:
                    log.warning("MISSING: %s", name)
                    return (0, 0)

                desired = dict(existing)
                for key in patch_delete:
                    desired.pop(str(key), None)
                desired.update(patch_set)
                current_desired = desired

                if configs_equal(desired, existing) and skip_if_no_change:
                    log.info("no changes (skip-if-no-change): %s", name)
                    return (0, 1)

                changes = config_key_changes(desired=desired, existing=existing)

                if dry_run:
                    log.info("[DRY-RUN] Would PATCH (GET+PUT): %s", name)
                    if show_structured_diff:
                        log.info(
                            "diff:\n%s",
                            format_config_key_changes(
                                changes, max_keys_per_section=diff_max_keys
                            ),
                        )
                    else:
                        diff_txt = config_unified_diff(
                            connector_name=name, desired=desired, existing=existing
                        )
                        diff_txt, trimmed = summarize_diff(diff_txt, max_lines=200)
                        log.info("diff%s:", " (truncated)" if trimmed else "")
                        log.info("```diff\n%s\n```", diff_txt)
                    return (1, 0)

                stage = "patch_update"
                enforce_runtime_mutation_guard_for_target(
                    ctx,
                    args,
                    target_obj,
                    command="connect patch",
                    dry_run=dry_run,
                )
                target_obj.client.update_connector(name, desired)
                log.info("patched: %s", name)
                return (1, 0)

            for execution_target in plan.targets:
                target = execution_target.target
                stage = "select_connectors"
                selected, missing = select_connectors(
                    connect=target.client, args=args, default_all=False
                )
                if missing:
                    raise ConfigError(f"Коннектор(ы) не найдены: {', '.join(missing)}")
                audit.event(
                    "connectors_selected",
                    payload={
                        "cluster": target.cluster.name,
                        "env": target.env.value,
                        "connectors": selected,
                    },
                )

                log_action_plan(
                    log,
                    action=f"PATCH {target.cluster.name}/{target.env.value}",
                    targets=selected,
                    dry_run=dry_run,
                )

                if conc.jobs <= 1:
                    results = [_patch_one(target, n) for n in selected]
                else:
                    results = map_fail_fast(
                        selected, lambda n: _patch_one(target, n), jobs=conc.jobs
                    )

                updated_total += sum(r[0] for r in results)
                skipped_total += sum(r[1] for r in results)

            log_action_summary(
                log, action="PATCH", done=updated_total, skipped=skipped_total
            )
            audit.set_result_code(0)
        return 0
    except Exception as exc:
        writer.write(
            env=str(getattr(args, "env")),
            stage=stage,
            error=exc,
            manifest_meta={
                "name": current_name,
                "cluster_group": target.cluster.name if target is not None else None,
            },
            prepared_manifest=(
                {"name": current_name, "config": current_desired}
                if current_name and current_desired is not None
                else None
            ),
            routing_payload=(
                build_target_routing_payload(target) if target is not None else None
            ),
            extra={
                "name": current_name,
                "cluster_group": (
                    target.cluster.name
                    if target is not None
                    else getattr(args, "cluster", None)
                ),
                "names_csv": getattr(args, "names", None),
                "regexp": list(getattr(args, "regexp", []) or []),
                "all": bool(getattr(args, "all", False)),
            },
        )
        raise


def register_parser(connect_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    s = connect_sub.add_parser(
        "patch",
        help="Patch (частичное обновление) конфига коннектора: GET+merge+PUT",
    )
    add_target_args(s)
    add_audit_args(s)
    add_selector_args(s, default_all=False)
    add_concurrency_args(s)
    add_runtime_break_glass_arg(s)

    s.add_argument(
        "--json",
        action="append",
        default=[],
        help="JSON patch объект inline. Можно несколько раз; последние значения побеждают. JSON null = удалить ключ.",
    )
    s.add_argument(
        "--json-file",
        dest="json_file",
        action="append",
        default=[],
        help="Путь к JSON файлу с patch объектом. Можно несколько раз. JSON null = удалить ключ.",
    )
    s.add_argument(
        "--set",
        action="append",
        default=[],
        help=(
            "Literal key=value запись. Можно несколько раз. Запятые внутри value "
            "сохраняются. value __DELETE__ = удалить ключ."
        ),
    )
    s.add_argument(
        "--set-csv",
        dest="set_csv",
        action="append",
        default=[],
        help=(
            "Legacy CSV key=value записи через запятую: k=v,k2=v2. "
            "Для table.include.list используйте обычный --set."
        ),
    )
    s.add_argument(
        "--set-file",
        dest="set_file",
        action="append",
        default=[],
        help="Файл с key=value (по строкам или CSV). Можно несколько раз. value __DELETE__ = удалить ключ.",
    )
    s.add_argument(
        "--stdin",
        action="store_true",
        default=False,
        help="Также прочитать patch из stdin (JSON или key=value). Применяется последним.",
    )
    s.add_argument(
        "--dry-run", action="store_true", help="Ничего не делать, только показать план"
    )
    add_yes_arg(
        s,
        help_text=(
            "Разрешить реальный fan-out patch для --cluster all. "
            "Для single-cluster patch поведение не меняет."
        ),
    )
    s.add_argument(
        "--diff",
        action="store_true",
        help="В --dry-run показать структурный diff (removed/added/changed keys) вместо unified diff",
    )
    s.add_argument(
        "--diff-max-keys",
        type=int,
        default=50,
        help="Лимит ключей на секцию для --diff (по умолчанию: 50)",
    )
    s.add_argument(
        "--skip-if-no-change",
        dest="skip_if_no_change",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Пропускать PUT, если итоговый конфиг не меняется (по умолчанию: да)",
    )
    add_failure_bundle_dir_arg(s, command="connect-patch")
    s.set_defaults(func=cmd_connect_patch)
    return s
