from __future__ import annotations

from dataclasses import dataclass

from ...exceptions import ConfigError


@dataclass(frozen=True)
class ConnectMutationSafetyPolicy:
    """Safety gate for mutating fan-out operations.

    A single-cluster mutation keeps the historical UX. A fan-out mutation
    (`--cluster all` / `*`) must be both targeted by connector selector and
    either dry-run or explicitly confirmed with `--yes`.
    """

    command: str

    def require_allowed(
        self,
        *,
        is_fanout: bool,
        has_selector: bool,
        dry_run: bool,
        assume_yes: bool,
    ) -> None:
        if not is_fanout:
            return
        if not has_selector:
            raise ConfigError(
                f"{self.command} with --cluster all requires an explicit selector: "
                "use --names a,b,c, --regexp <re>, or --all intentionally."
            )
        if dry_run or assume_yes:
            return
        raise ConfigError(
            f"{self.command} with --cluster all is a fan-out mutation. "
            "Run with --dry-run first, or pass --yes for the actual mutation."
        )


__all__ = ["ConnectMutationSafetyPolicy"]
