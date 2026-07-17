from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple


@dataclass(frozen=True)
class PreviewConfig:
    """Настройки предпросмотра для side-effect команд."""

    list_limit: int = 20


def limit_items(items: Sequence[str], *, limit: int) -> Tuple[List[str], int]:
    """Вернуть (первые limit элементов, сколько осталось)."""

    if limit <= 0:
        return list(items), 0
    shown = list(items[:limit])
    tail = max(0, len(items) - len(shown))
    return shown, tail


def log_action_plan(
    log,
    *,
    action: str,
    targets: Sequence[str],
    dry_run: bool,
    cfg: PreviewConfig | None = None,
) -> None:
    """Единый формат preview для side-effect команд.

    Требования UX:
      - target cluster banner печатается отдельно (resolve_target)
      - список коннекторов: limit + "… и ещё X"
      - action summary
    """

    cfg = cfg or PreviewConfig()
    suffix = " [DRY-RUN]" if dry_run else ""
    log.info("%s plan: connectors=%s%s", action, len(targets), suffix)

    shown, tail = limit_items(list(targets), limit=cfg.list_limit)
    for n in shown:
        log.info(" - %s", n)
    if tail:
        log.info("… и ещё %s", tail)


def log_action_summary(
    log, *, action: str, done: int, skipped: int = 0, failed: int = 0
) -> None:
    """Короткий итог выполнения."""

    parts = [f"done={done}"]
    if skipped:
        parts.append(f"skipped={skipped}")
    if failed:
        parts.append(f"failed={failed}")
    log.info("%s done: %s", action, " ".join(parts))
