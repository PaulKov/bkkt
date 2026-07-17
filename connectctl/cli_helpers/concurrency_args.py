from __future__ import annotations

import argparse


def add_concurrency_args(p: argparse.ArgumentParser, *, default_jobs: int = 1) -> None:
    """Добавить флаги параллелизма и rate limiting.

    Используется в нескольких командах:
    - apply
    - export
    - connect patch/restart/delete

    Принцип:
    - по умолчанию jobs=1 (без изменения поведения)
    - rate-limit по умолчанию не задаётся тут, а вычисляется в ConcurrencyOptions.from_args
      (там есть безопасный auto-default при jobs>1)
    """

    p.add_argument(
        "--jobs",
        type=int,
        default=default_jobs,
        help=(
            "Параллелизм (кол-во потоков) для массовых операций. "
            f"По умолчанию: {default_jobs}"
            + (" (последовательно)" if default_jobs == 1 else "")
        ),
    )
    p.add_argument(
        "--rate-limit-per-second",
        dest="rate_limit_per_second",
        type=float,
        default=None,
        help=(
            "Ограничение REST запросов в секунду (RPS) ко всем Connect URL вместе. "
            "Если не задано и --jobs > 1, включается безопасный лимит (по умолчанию ~5 RPS). "
            "0 = выключить ограничение."
        ),
    )
