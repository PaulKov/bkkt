from __future__ import annotations

import argparse

from ...cli_helpers.config_scope_args import add_config_scope_args
from ...cli_helpers.output_args import add_output_format_args
from ...logging_utils import get_logger
from ...services.config.clusters_service import ConfigClustersService


def cmd_config_clusters(args: argparse.Namespace, *, ctx, logger=None) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    svc = ConfigClustersService(ctx=ctx, logger=log)
    return int(svc.run(args))


def register_parser(config_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = config_sub.add_parser(
        "clusters",
        help="Показать cluster groups/env/Connect URLs/Kafka hosts из connectctl.yaml",
    )
    add_config_scope_args(p)
    p.add_argument(
        "--show-render-vars",
        action="store_true",
        help=(
            "Показать render.vars и render.prune_config_keys для выбранных scopes "
            "(секреты маскируются эвристикой по имени ключа)."
        ),
    )
    p.add_argument(
        "--hide-kafka-bootstrap",
        action="store_true",
        help="Не показывать колонку Kafka bootstrap в text-выводе",
    )
    p.add_argument(
        "--hide-schema-registry",
        action="store_true",
        help="Не показывать колонку Schema Registry в text-выводе",
    )
    p.add_argument(
        "--no-provenance",
        action="store_true",
        help="Не печатать Notes/provenance блок в text-выводе",
    )
    p.add_argument(
        "--view",
        choices=["short", "long", "details"],
        default="long",
        help="Text view mode: short|long|details. По умолчанию: long",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_config_clusters)
    return p
