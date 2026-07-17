from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Optional

from connectctl.cli_helpers.status_format import (
    format_status_long_text,
    status_to_payload,
)

from ..cli_helpers.output_args import add_output_format_args
from ..logging_utils import get_logger
from ..output import OutputFormat, resolve_output_format, write_payload
from ..services.connector_name_meta import parse_connector_name_meta
from ..models import ConnectorStatus

from .connect.common import add_target_args, resolve_target


def cmd_get_connector(args: argparse.Namespace, *, ctx, logger=None) -> int:
    """Получить конфиг (и опционально статус) конкретного коннектора."""

    log = get_logger(logger or getattr(ctx, "logger", None))
    target = resolve_target(ctx, args, logger=log)

    name = str(getattr(args, "name", "") or "").strip()
    if not name:
        log.error("Не задано имя коннектора")
        return 2

    include_meta = bool(getattr(args, "meta", False))
    status_mode = str(getattr(args, "status", "none") or "none").strip().lower()
    if status_mode not in {"none", "short", "long"}:
        log.warning("Неизвестный --status=%r, использую 'none'", status_mode)
        status_mode = "none"

    out_fmt = resolve_output_format(args)

    cfg: Optional[Dict[str, Any]] = target.client.get_config_optional(name)
    if cfg is None:
        if out_fmt == OutputFormat.text:
            log.warning("Коннектор не найден: %s", name)
        else:
            not_found_payload = {
                "cluster": target.cluster.name,
                "env": target.env,
                "name": name,
                "found": False,
            }
            write_payload(not_found_payload, fmt=out_fmt)
        return 1

    payload: Dict[str, Any] = {
        "cluster": target.cluster.name,
        "env": target.env,
        "name": name,
        "found": True,
        "config": cfg,
    }

    if include_meta:
        payload["meta"] = parse_connector_name_meta(name).to_dict()

    st_obj: Optional[ConnectorStatus] = None
    if status_mode != "none":
        try:
            st_obj = target.client.get_status(name)
            payload["status"] = status_to_payload(
                st_obj,
                mode=status_mode,
                include_raw=bool(getattr(args, "raw_status_json", False))
                and status_mode == "long",
            )
        except Exception as e:
            payload["status_error"] = f"{type(e).__name__}: {e}"

    if out_fmt == OutputFormat.text:
        log.info("Connector: %s", name)
        if include_meta:
            meta_val = payload.get("meta")
            m: Dict[str, Any] = meta_val if isinstance(meta_val, dict) else {}
            log.info(
                "Meta: env=%s domain=%s dataset=%s type=%s system=%s layer=%s mode=%s kind=%s index=%s",
                m.get("env"),
                m.get("domain"),
                m.get("dataset"),
                m.get("integration_type"),
                m.get("system"),
                m.get("layer"),
                m.get("source_mode"),
                m.get("sink_kind"),
                m.get("index"),
            )

        if status_mode != "none":
            if payload.get("status_error"):
                log.warning("Status error: %s", payload["status_error"])
            elif st_obj is not None:
                if status_mode == "long":
                    log.info(
                        "%s",
                        format_status_long_text(
                            name,
                            st_obj,
                            include_raw=bool(getattr(args, "raw_status_json", False)),
                        ),
                    )
                else:
                    status_val = payload.get("status")
                    st: Dict[str, Any] = (
                        status_val if isinstance(status_val, dict) else {}
                    )
                    log.info(
                        "Status: connector=%s tasks=%s ok=%s",
                        st.get("connector_state"),
                        st.get("task_states"),
                        st.get("ok"),
                    )

        log.info("Config:")
        log.info(json.dumps(cfg, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    write_payload(payload, fmt=out_fmt)
    return 0


def _add_args(p: argparse.ArgumentParser) -> None:
    add_target_args(p)
    add_output_format_args(p)
    p.add_argument("name", help="Имя коннектора")
    p.add_argument(
        "--status",
        choices=["none", "short", "long"],
        default="none",
        help="none=только config, short=краткий статус, long=подробный статус (tasks/trace); raw — по флагу",
    )
    p.add_argument(
        "--raw-status-json",
        action="store_true",
        default=False,
        help="(опционально) В режиме --status long дополнительно включить raw JSON статуса (как вернул Kafka Connect)",
    )
    p.add_argument(
        "--meta",
        action="store_true",
        help="Показать метаданные, распарсенные из имени коннектора",
    )
    p.set_defaults(func=cmd_get_connector)


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p_main = subparsers.add_parser(
        "get-connector",
        help="Показать config (и опционально status) конкретного коннектора",
    )
    _add_args(p_main)
    return p_main
