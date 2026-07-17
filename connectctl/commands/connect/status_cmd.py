from __future__ import annotations

import argparse
import time
from datetime import datetime
from collections import Counter

from ...logging_utils import get_logger
from ...cli_helpers.status_format import (
    format_status_short_line,
    format_status_long_text,
    status_to_payload,
)
from ...cli_helpers.output_args import add_output_format_args
from ...exceptions import ConfigError
from .common import (
    add_selector_args,
    add_target_args,
    resolve_target_plan,
    select_connectors,
)
from ...output import is_machine_output, resolve_output_format, write_payload


def cmd_connect_status(args: argparse.Namespace, *, ctx, logger=None) -> int:
    """Показать статусы коннекторов (по фильтру или все)."""

    log = get_logger(logger or getattr(ctx, "logger", None))

    watch = bool(getattr(args, "watch", False))
    until_healthy = bool(getattr(args, "until_healthy", False))
    if until_healthy and not watch:
        # UX: если пользователь попросил ждать healthy — логично включить watch.
        watch = True

    interval_s = float(getattr(args, "interval_seconds", 2.0))
    timeout_s = float(getattr(args, "timeout_seconds", 300.0))
    output_fmt = resolve_output_format(args)
    if watch and is_machine_output(output_fmt):
        raise ConfigError("--watch поддерживает только text output")

    plan = resolve_target_plan(ctx, args, logger=log)

    start = time.monotonic()
    warned_missing: set[tuple[str, str]] = set()

    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if watch:
            log.info("--- STATUS %s ---", now)

        status_mode = str(getattr(args, "status", "short") or "short").lower()
        raw_json = bool(getattr(args, "raw_json", False))

        payload_targets: list[dict[str, object]] = []
        total_connectors = 0
        total_ok = 0
        ok_all = True
        for execution_target in plan.targets:
            target = execution_target.target
            selected, missing = select_connectors(
                connect=target.client, args=args, default_all=True
            )
            for name in missing:
                missing_key = (target.cluster.name, name)
                if missing_key not in warned_missing:
                    log.warning(
                        "MISSING %s/%s: %s", target.cluster.name, target.env.value, name
                    )
                    warned_missing.add(missing_key)

            statuses = {}
            errors: list[dict[str, str]] = []
            for name in selected:
                if name in missing:
                    continue
                try:
                    st_obj = target.client.get_status(name)
                    statuses[name] = st_obj
                    total_connectors += 1
                    total_ok += 1 if st_obj.ok else 0
                    ok_all = ok_all and bool(st_obj.ok)
                except Exception as e:
                    ok_all = False
                    errors.append({"name": name, "error": str(e)})
                    log.error(
                        "%s/%s %s: ERROR: %s",
                        target.cluster.name,
                        target.env.value,
                        name,
                        e,
                    )

            if not is_machine_output(output_fmt):
                if plan.is_fanout:
                    log.info("--- %s/%s ---", target.cluster.name, target.env.value)
                if status_mode == "stats":
                    conn_counts: Counter[str] = Counter()
                    task_counts: Counter[str] = Counter()
                    for st in statuses.values():
                        conn_counts[st.connector_state or "UNKNOWN"] += 1
                        for ts in st.task_states or ():
                            task_counts[ts or "UNKNOWN"] += 1
                    log.info("Connector states: %s", dict(conn_counts))
                    log.info("Task states: %s", dict(task_counts))
                elif status_mode == "long":
                    for name, st_display in statuses.items():
                        log.info(
                            "%s",
                            format_status_long_text(
                                name, st_display, include_raw=raw_json
                            ),
                        )
                else:
                    for name, st_display in statuses.items():
                        log.info("%s", format_status_short_line(name, st_display))

            payload_targets.append(
                {
                    "cluster_group": target.cluster.name,
                    "env": target.env.value,
                    "urls": list(target.cluster.urls),
                    "aliases": list(execution_target.aliases),
                    "selected": list(selected),
                    "missing": list(missing),
                    "errors": errors,
                    "connectors": [
                        {
                            "name": name,
                            "cluster_group": target.cluster.name,
                            "env": target.env.value,
                            "status": status_to_payload(
                                st_obj,
                                mode=(
                                    "long"
                                    if status_mode in {"long", "stats"}
                                    else "short"
                                ),
                                include_raw=raw_json,
                            ),
                        }
                        for name, st_obj in statuses.items()
                    ],
                }
            )

        if total_connectors == 0:
            log.info("Нет коннекторов по заданному фильтру.")
            if not is_machine_output(output_fmt):
                return 0

        if is_machine_output(output_fmt):
            write_payload(
                {
                    "command": "connect status",
                    "env": str(getattr(args, "env")),
                    "status_mode": status_mode,
                    "counts": {
                        "targets": len(plan.targets),
                        "connectors": total_connectors,
                        "ok": total_ok,
                        "not_ok": total_connectors - total_ok,
                    },
                    "targets": payload_targets,
                },
                fmt=output_fmt,
            )

        if not watch:
            return 0

        if until_healthy:
            if ok_all:
                log.info("Все выбранные коннекторы healthy (RUNNING).")
                return 0

            elapsed = time.monotonic() - start
            if elapsed >= timeout_s:
                log.error(
                    "Не дождались healthy состояния за %.1f секунд (timeout).",
                    timeout_s,
                )
                return 2

        try:
            time.sleep(max(0.1, interval_s))
        except KeyboardInterrupt:
            log.warning("Остановлено пользователем (Ctrl+C).")
            return 130


def register_parser(connect_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    s = connect_sub.add_parser("status", help="Показать статус коннекторов")
    add_target_args(s)
    add_selector_args(s, default_all=True)
    add_output_format_args(s)
    s.add_argument(
        "--status",
        choices=["short", "long", "stats"],
        default="short",
        help="short=одна строка на коннектор, long=подробно (tasks/trace), stats=агрегация по состояниям",
    )
    s.add_argument(
        "--raw-json",
        action="store_true",
        default=False,
        help="(опционально) В режиме --status long дополнительно печатать raw JSON статуса (как вернул Kafka Connect)",
    )
    s.add_argument("--watch", action="store_true", help="Обновлять статус в цикле")
    s.add_argument(
        "--interval-seconds",
        dest="interval_seconds",
        type=float,
        default=2.0,
        help="Интервал обновления для --watch (в секундах)",
    )
    s.add_argument(
        "--until-healthy",
        action="store_true",
        help="Ждать, пока все выбранные коннекторы станут healthy (RUNNING)",
    )
    s.add_argument(
        "--timeout-seconds",
        dest="timeout_seconds",
        type=float,
        default=300.0,
        help="Таймаут ожидания healthy для --until-healthy (в секундах)",
    )
    s.set_defaults(func=cmd_connect_status)
    return s
