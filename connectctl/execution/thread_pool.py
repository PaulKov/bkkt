from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Generic, Iterable, Optional, TypeVar, cast


T = TypeVar("T")
R = TypeVar("R")


@dataclass(frozen=True)
class TaskResult(Generic[T, R]):
    item: T
    value: Optional[R] = None
    error: Optional[BaseException] = None


def map_collect(
    items: Iterable[T], fn: Callable[[T], R], *, jobs: int
) -> list[TaskResult[T, R]]:
    """Execute fn(item) over items, collecting per-item results.

    - In sequential mode (jobs <= 1) keeps original ordering.
    - In parallel mode ordering is preserved to match the input order.
    """

    seq = list(items)
    results: list[TaskResult[T, R]] = []

    if jobs <= 1:
        for item in seq:
            try:
                value = fn(item)
                results.append(TaskResult(item=item, value=value))
            except BaseException as e:
                results.append(TaskResult(item=item, error=e))
        return results

    with ThreadPoolExecutor(max_workers=int(jobs)) as pool:
        fut_to_idx = {pool.submit(fn, item): i for i, item in enumerate(seq)}
        tmp: list[TaskResult[T, R]] = [
            TaskResult(item=seq[i], error=RuntimeError("pending"))
            for i in range(len(seq))
        ]
        for fut in as_completed(fut_to_idx):
            idx = fut_to_idx[fut]
            item = seq[idx]
            try:
                tmp[idx] = TaskResult(item=item, value=fut.result())
            except BaseException as e:
                tmp[idx] = TaskResult(item=item, error=e)
        return tmp


def map_fail_fast(items: Iterable[T], fn: Callable[[T], R], *, jobs: int) -> list[R]:
    """Execute fn(item) over items and fail immediately on first exception.

    Ordering of results matches the input ordering.
    """

    seq = list(items)
    if jobs <= 1:
        return [fn(it) for it in seq]

    results: list[Optional[R]] = [None] * len(seq)
    with ThreadPoolExecutor(max_workers=int(jobs)) as pool:
        fut_to_idx = {pool.submit(fn, item): i for i, item in enumerate(seq)}
        for fut in as_completed(fut_to_idx):
            idx = fut_to_idx[fut]
            results[idx] = fut.result()  # will raise

    return cast(list[R], results)
