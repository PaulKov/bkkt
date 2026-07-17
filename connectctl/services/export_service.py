from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from ..app.context import CliContext
from ..exceptions import ConfigError
from ..logging_utils import get_logger
from ..repo import ConnectorRepo
from ..adapters.filesystem_threadsafe import ThreadSafeFileSystem
from ..execution import ConcurrencyOptions, RateLimiter
from .export.options import (
    parse_filters,
    parse_iceberg_scaffolding,
    parse_name_overrides,
    parse_placement_overrides,
    parse_reuse,
    parse_variants,
    resolve_flags,
    resolve_selection,
)
from .export.runner import ExportRunner


@dataclass
class ExportService:
    """Высокоуровневый сервис для `connectctl export`.

    CLI-адаптер (commands/export_cmd.py) остаётся маленьким.
    Тут — операционная логика экспорта.

    DI:
    - зависимости берём из CliContext
    - logger optional, при отсутствии используется ctx.logger
    """

    ctx: CliContext
    logger: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        self.log = get_logger(self.logger or self.ctx.logger)

    def run(self, args) -> int:
        repo_root = self.ctx.repo_root
        settings = self.ctx.settings

        conc = ConcurrencyOptions.from_args(args)
        throttle = (
            RateLimiter(conc.rate_limit_per_second, burst=conc.burst)
            if conc.rate_limit_per_second > 0
            else None
        )

        env = self.ctx.env(getattr(args, "env"))
        cluster_name = getattr(args, "cluster", None)
        target = self.ctx.connect_target(env, cluster_name, throttle=throttle)

        # Единый баннер с URL — как в остальных командах.
        self.ctx.print_cluster_banner(target)

        fs = ThreadSafeFileSystem(self.ctx.fs) if conc.jobs > 1 else self.ctx.fs
        repo = ConnectorRepo(settings.repo, fs=fs)
        connect = target.client

        self.log.info(
            "Export target: cluster=%s env=%s urls=%s",
            target.cluster.name,
            env.value,
            ", ".join(target.cluster.urls),
        )

        # 1) Разбор опций
        variants = parse_variants(args=args)
        filters = parse_filters(args=args)
        placement_overrides = parse_placement_overrides(args=args)
        reuse = parse_reuse(args=args, repo_root=repo_root)
        iceberg = parse_iceberg_scaffolding(args=args)
        flags = resolve_flags(args=args, settings=settings)

        # 2) Список коннекторов
        if bool(getattr(args, "all", False)):
            all_names = connect.list_connectors()
            selection = resolve_selection(
                args=args, names_from_cli=[], all_names=list(all_names)
            )
        else:
            selection = resolve_selection(
                args=args, names_from_cli=list(getattr(args, "names", None) or [])
            )

        name_overrides = parse_name_overrides(args=args, selection=selection)

        # Safety: prevent two different remote connectors being exported into the same repo name.
        if not selection.all and name_overrides:
            exported_names = [name_overrides.get(n, n) for n in selection.names]
            dups = sorted({x for x in exported_names if exported_names.count(x) > 1})
            if dups:
                raise ConfigError(
                    "--as-name приводит к коллизии: несколько коннекторов будут экспортированы в одно и то же имя: "
                    f"{dups}. Исправьте mapping (remote->new_name)."
                )

        runner = ExportRunner(
            repo_root=repo_root,
            repo=repo,
            settings=settings,
            connect=connect,
            logger=self.log,
        )

        exported, skipped = runner.run(
            env=env,
            selection=selection,
            filters=filters,
            placement_overrides=placement_overrides,
            flags=flags,
            variants=variants,
            iceberg=iceberg,
            override_only_paths=reuse.override_only_paths,
            name_overrides=name_overrides,
            jobs=conc.jobs,
        )

        self.log.info("Export done: exported=%s skipped=%s", exported, skipped)
        return 0
