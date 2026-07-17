from __future__ import annotations

import argparse

from ...cli_helpers.output_args import add_output_format_args
from ...logging_utils import get_logger
from ...services.repo_migrate.service import RepoMigrateConnectorDirService


def cmd_repo_migrate_connector_dir(
    args: argparse.Namespace, *, ctx, logger=None
) -> int:
    log = get_logger(logger or getattr(ctx, "logger", None))
    svc = RepoMigrateConnectorDirService(ctx=ctx, logger=log)
    return int(svc.run(args))


def register_parser(repo_sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = repo_sub.add_parser(
        "migrate-connector-dir",
        help="Нормализовать connector_dir к шаблону connector_<domain>__<dataset>{__<suffix>}",
    )
    p.add_argument(
        "--scope",
        choices=["all", "changed"],
        default="all",
        help="Область миграции: all=весь репозиторий, changed=только затронутые git diff (base/head).",
    )
    p.add_argument("--base", help="Base git sha (для scope=changed; по умолчанию auto)")
    p.add_argument("--head", help="Head git sha (для scope=changed; по умолчанию HEAD)")
    p.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Сколько элементов плана печатать (top-N). Остальные будут свернуты как '… и ещё X…'.",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Выполнить переименование (по умолчанию команда работает как dry-run и только показывает план).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Явно включить dry-run (ничего не менять, только показать план).",
    )
    p.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Не спрашивать подтверждение при --apply.",
    )
    p.add_argument(
        "--on-conflict",
        choices=["error", "skip", "suffix"],
        default="error",
        help=(
            "Что делать, если целевой каталог уже существует: "
            "error=ошибка (default), skip=пропустить, suffix=добавить __migrated для уникальности."
        ),
    )
    p.add_argument(
        "--update-references",
        action="store_true",
        help="Попытаться обновить текстовые ссылки на старые пути (README/docs/ci).",
    )
    p.add_argument(
        "--update-references-scope",
        default="docs,ci",
        help=(
            "Где искать ссылки для обновления (через запятую): docs,ci,vscode,all. "
            "default: docs,ci"
        ),
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_repo_migrate_connector_dir)
    return p
