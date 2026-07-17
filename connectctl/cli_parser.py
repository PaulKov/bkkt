from __future__ import annotations

import argparse

from . import __version__
from .cli_helpers.explicit_args import ExplicitTrackingArgumentParser
from .commands.registry import register_all


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser.

    Refactor stage 2: each command module registers its own parser and arguments.
    """

    p = ExplicitTrackingArgumentParser(
        # Do not hardcode `prog`: argparse will pick up the actual entrypoint name
        # (connectctl / bkkt), which is more user-friendly.
        allow_abbrev=False,
        description="BKKT — Best Kafka Connectors Tool (GitOps CI/CD для Kafka Connect коннекторов)",
    )
    p.add_argument(
        "--repo-root", default=".", help="Корень репозитория (по умолчанию: .)"
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"bkkt {__version__}",
        help="Print BKKT version and exit",
    )
    p.add_argument(
        "--config",
        default=None,
        help="Путь к connectctl.yaml (по умолчанию ищется в репозитории)",
    )
    p.add_argument(
        "--explain-routing",
        action="store_true",
        help="Пояснить выбор cluster group для коннектора: какой слой/тег/дефолт победил",
    )
    p.add_argument(
        "--explain-vars",
        action="store_true",
        help="Пояснить происхождение config-ключей: из какого слоя взято итоговое значение",
    )
    p.add_argument(
        "--explain-vars-keys",
        default=None,
        help=(
            "Фильтр ключей для --explain-vars. "
            "Можно указать несколько паттернов через запятую (regex или подстрока). "
            "Пример: 'snapshot|transforms,errors'"
        ),
    )
    p.add_argument(
        "--explain-vars-max",
        type=int,
        default=200,
        help="Максимум ключей для вывода в --explain-vars (0 = без лимита). По умолчанию: 200",
    )

    sub = p.add_subparsers(dest="cmd", required=True)
    register_all(sub)

    return p
