from __future__ import annotations

import argparse

from ...logging_utils import get_logger
from ...services.docs.generate_cli_reference_service import GenerateCliReferenceService


def cmd_docs_generate_cli_reference(
    args: argparse.Namespace, *, ctx, logger=None
) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    svc = GenerateCliReferenceService(ctx=ctx, logger=log)
    return int(svc.run(args))


def register_parser(docs_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = docs_sub.add_parser(
        "generate-cli-reference",
        help="Сгенерировать docs/CLI_REFERENCE*.md из argparse/--help (и опционально проверить актуальность)",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Только проверить, что docs актуальны (не перезаписывать). Exit!=0 если отличаются.",
    )

    # Diagnostics for CI / local debugging.
    p.add_argument(
        "--show-diff",
        action="store_true",
        help="При --check вывести unified diff для несовпадающих файлов.",
    )
    p.add_argument(
        "--diff-lines",
        type=int,
        default=200,
        help="Сколько строк diff показывать на файл (default: 200, 0 = не выводить).",
    )
    p.add_argument(
        "--target",
        choices=["all", "md"],
        default="all",
        help="Какие файлы генерировать/проверять: all (default) | md",
    )
    p.add_argument(
        "--docs-dir",
        default="docs",
        help="Каталог docs в репозитории (default: docs)",
    )
    p.set_defaults(func=cmd_docs_generate_cli_reference, requires_config=False)
    return p
