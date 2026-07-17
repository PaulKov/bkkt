"""Утилиты выполнения (concurrency / rate limiting).

Этот пакет содержит маленькие, DI-friendly компоненты:
- ConcurrencyOptions: единый парсинг --jobs/--rate-limit-per-second из CLI args
- RateLimiter: потокобезопасный token-bucket limiter
- thread_pool: минимальные helper'ы для параллельного выполнения задач

Задача: ускорить массовые операции (apply/export/connect ...) безопасно,
не ломая архитектуру и не размазывая ThreadPoolExecutor по всему коду.
"""

from .concurrency import ConcurrencyOptions
from .rate_limiter import RateLimiter
from .thread_pool import map_collect, map_fail_fast

__all__ = [
    "ConcurrencyOptions",
    "RateLimiter",
    "map_collect",
    "map_fail_fast",
]
