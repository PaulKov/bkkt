from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class RateLimiter:
    """Потокобезопасный token-bucket rate limiter.

    Используется для ограничения нагрузки на Kafka Connect REST API.

    Важные свойства:
    - rate_per_second <= 0 => acquire() становится no-op
    - thread-safe (через Lock)
    - burst задаёт максимальный размер "ведра" (сколько токенов можно накопить)

    DI:
    - clock_fn/sleep_fn инжектируются для детерминированных тестов
    """

    rate_per_second: float
    burst: int = 1
    clock_fn: Callable[[], float] = time.monotonic
    sleep_fn: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._tokens = float(max(0, self.burst))
        self._last_ts = float(self.clock_fn())

    def acquire(self, tokens: float = 1.0) -> None:
        """Заблокироваться/подождать, пока не появятся токены."""

        if self.rate_per_second <= 0:
            return

        if tokens <= 0:
            return

        while True:
            sleep_for = 0.0
            with self._lock:
                now = float(self.clock_fn())
                elapsed = max(0.0, now - self._last_ts)
                self._last_ts = now

                # refill
                self._tokens = min(
                    float(self.burst),
                    self._tokens + elapsed * float(self.rate_per_second),
                )

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return

                # Need to wait until enough tokens appear.
                missing = tokens - self._tokens
                sleep_for = missing / float(self.rate_per_second)

                # Reset tokens to 0 so we don't underflow.
                self._tokens = 0.0

            # sleep outside lock
            if sleep_for > 0:
                self.sleep_fn(sleep_for)


__all__ = ["RateLimiter"]
