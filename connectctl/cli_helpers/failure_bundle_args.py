from __future__ import annotations

import argparse


def add_failure_bundle_dir_arg(
    parser: argparse.ArgumentParser, *, command: str
) -> None:
    parser.add_argument(
        "--failure-bundle-dir",
        dest="failure_bundle_dir",
        default=None,
        help=(
            "Каталог для diagnostic failure bundles. "
            "При ошибке BKKT сохранит prepared manifest, routing и error payload "
            f"в отдельный подкаталог (по умолчанию: artifacts/failure-bundles/{command})."
        ),
    )
