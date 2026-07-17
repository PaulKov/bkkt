from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from ...app.context import CliContext
from ...logging_utils import get_logger

from .options import parse_init_options
from .scaffold import scaffold_repo_files


@dataclass
class InitService:
    """Service for `connectctl init`.

    This command scaffolds a connector directory and minimal env manifests.

    Env manifests are name-only JSON files:
      {"name": "<connector.name>"}

    Heavy config should live in all.json and higher-level layers.
    """

    ctx: CliContext
    logger: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        self.log = get_logger(self.logger or self.ctx.logger)

    def run(self, args) -> int:
        opts = parse_init_options(args=args, ctx=self.ctx, log=self.log)
        scaffold_repo_files(opts=opts, log=self.log)
        return 0
