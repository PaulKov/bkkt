from __future__ import annotations

import argparse


def add_config_scope_args(
    parser: argparse.ArgumentParser,
    *,
    require_env: bool = False,
    require_cluster_group: bool = False,
) -> None:
    """Add config inventory scope selectors.

    Config commands operate on `connectctl.yaml`, where a scope can include
    many cluster groups and envs. Therefore these flags are repeatable and
    accept CSV values, unlike live commands where `--cluster` means one target.
    """

    parser.add_argument(
        "--cluster-group",
        "--cluster",
        dest="cluster_group",
        action="append",
        default=None,
        required=require_cluster_group,
        help=(
            "Фильтр по cluster group (можно несколько раз или через запятую). "
            "Alias: --cluster."
        ),
    )
    parser.add_argument(
        "--env",
        action="append",
        default=None,
        required=require_env,
        help=(
            "Фильтр по окружению (dev|stage|prod). "
            "Можно несколько раз или через запятую."
        ),
    )
