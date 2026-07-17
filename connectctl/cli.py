from __future__ import annotations

from typing import Optional, Sequence

from .cli_parser import build_parser
from .cli_support import (
    _split_patch_set_and_delete as _split_patch_set_and_delete,
    _validate_manifest as _validate_manifest,
)
from .exceptions import ConnectCtlError
from .logging_utils import get_logger, setup_logging
from .app.context import CliContext
from .services.failure_bundle import format_inline_remediation_lines


def main(argv: Optional[Sequence[str]] = None) -> int:
    logger = setup_logging()

    parser = build_parser()

    # Optional: shell autocompletion via argcomplete (bkkt completion --shell ...).
    try:  # pragma: no cover (depends on shell env)
        import argcomplete

        argcomplete.autocomplete(parser)
    except Exception:
        # Autocompletion must never break normal execution.
        pass
    args = parser.parse_args(argv)

    require_config = bool(getattr(args, "requires_config", True))
    ctx = CliContext.from_args(args, logger=logger, require_config=require_config)

    try:
        # OOP-dispatch: argparse subparser stores a Command object in `_command`.
        cmd = getattr(args, "_command", None)
        if cmd is not None:
            return int(cmd.run(args, ctx))

        # Backward-compatible fallback: old parsers used `func=...`.
        func = getattr(args, "func", None)
        if callable(func):
            return int(func(args, ctx=ctx, logger=logger))

        raise ConnectCtlError("Не удалось определить команду для выполнения")
    except ConnectCtlError as e:
        get_logger(logger).error(str(e))
        for line in format_inline_remediation_lines(e):
            get_logger(logger).error("%s", line)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
