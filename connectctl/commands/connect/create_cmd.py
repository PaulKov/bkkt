from __future__ import annotations

import argparse

from ...cli_support import _extract_name_and_config, _read_raw_json
from ...cli_helpers.failure_bundle_args import add_failure_bundle_dir_arg
from ...cli_helpers.side_effect_preview import log_action_plan, log_action_summary
from ...exceptions import ConfigError
from ...logging_utils import get_logger
from ...services.failure_bundle import FailureBundleWriter
from .common import (
    add_runtime_break_glass_arg,
    add_target_args,
    build_target_routing_payload,
    enforce_runtime_mutation_guard,
    resolve_target,
)


def cmd_connect_create(args: argparse.Namespace, *, ctx, logger=None) -> int:
    """Создать коннектор из сырого JSON (stdin или файл)."""

    log = get_logger(logger or getattr(ctx, "logger", None))
    writer = FailureBundleWriter.from_args(
        command="connect-create",
        repo_root=ctx.repo_root,
        fs=ctx.fs,
        args=args,
    )

    stage = "resolve_target"
    target = None
    name = None
    cfg = None
    try:
        target = resolve_target(ctx, args, logger=log)

        stage = "read_payload"
        raw_obj = _read_raw_json(getattr(args, "src", "-"))
        name, cfg = _extract_name_and_config(raw_obj, getattr(args, "name", None))

        dry_run = bool(getattr(args, "dry_run", False))

        stage = "fetch_config"
        existing = target.client.get_config_optional(name)
        if existing is not None:
            raise ConfigError(f"Коннектор уже существует: {name} (используйте update)")

        log_action_plan(log, action="CREATE", targets=[name], dry_run=dry_run)
        log.info("Create payload: name=%s config_keys=%s", name, len(cfg))
        if dry_run:
            log.info("[DRY-RUN] Would POST /connectors with name=%s", name)
            log_action_summary(log, action="CREATE", done=0, skipped=1)
            return 0

        enforce_runtime_mutation_guard(
            ctx, args, command="connect create", dry_run=dry_run
        )
        stage = "create"
        target.client.create_connector(name, cfg)
        log.info("created: %s", name)
        log_action_summary(log, action="CREATE", done=1, skipped=0)
        return 0
    except Exception as exc:
        writer.write(
            env=str(getattr(args, "env")),
            stage=stage,
            error=exc,
            manifest_meta={
                "name": name,
                "cluster_group": target.cluster.name if target is not None else None,
            },
            prepared_manifest=(
                {"name": name, "config": cfg} if name and cfg is not None else None
            ),
            routing_payload=(
                build_target_routing_payload(target) if target is not None else None
            ),
            extra={
                "name": name,
                "cluster_group": (
                    target.cluster.name
                    if target is not None
                    else getattr(args, "cluster", None)
                ),
                "input_src": getattr(args, "src", "-"),
            },
        )
        raise


def register_parser(connect_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    s = connect_sub.add_parser("create", help="Создание коннектора из сырого JSON")
    add_target_args(s)
    add_runtime_break_glass_arg(s)
    s.add_argument(
        "--name", default=None, help="Имя коннектора (если payload не содержит 'name')"
    )
    s.add_argument(
        "--dry-run", action="store_true", help="Ничего не делать, только показать план"
    )
    s.add_argument(
        "src",
        nargs="?",
        default="-",
        help="JSON файл или '-' для stdin (по умолчанию: -)",
    )
    add_failure_bundle_dir_arg(s, command="connect-create")
    s.set_defaults(func=cmd_connect_create)
    return s
