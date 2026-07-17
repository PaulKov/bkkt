from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..exceptions import ConfigError


@dataclass(frozen=True)
class ConcurrencyOptions:
    """Единые настройки параллелизма и rate limiting.

    Логика "по умолчанию" сделана безопасной и предсказуемой:
    - jobs=1 => по умолчанию без rate limiting
    - jobs>1 и rate не задан => включаем умеренный rate limiting (по умолчанию 5 rps)
      чтобы не перегружать Kafka Connect.

    Пользователь может явно отключить лимит: --rate-limit-per-second 0
    """

    jobs: int = 1
    rate_limit_per_second: float = 0.0
    burst: int = 1

    @classmethod
    def from_args(
        cls,
        args: Any,
        *,
        default_jobs: int = 1,
        default_rate_if_parallel: float = 5.0,
    ) -> "ConcurrencyOptions":
        jobs_raw = getattr(args, "jobs", None)
        jobs = int(jobs_raw) if jobs_raw is not None else int(default_jobs)
        if jobs < 1:
            raise ConfigError("--jobs должен быть >= 1")

        rate_raw: Optional[float] = getattr(args, "rate_limit_per_second", None)
        if rate_raw is None:
            rate = float(default_rate_if_parallel if jobs > 1 else 0.0)
        else:
            try:
                rate = float(rate_raw)
            except (TypeError, ValueError) as e:
                raise ConfigError("--rate-limit-per-second должен быть числом") from e

        if rate < 0:
            raise ConfigError("--rate-limit-per-second должен быть >= 0")

        # Пока burst не экспонируем как CLI флаг, но оставляем на будущее.
        burst_raw = getattr(args, "rate_burst", None)
        burst = int(burst_raw) if burst_raw is not None else max(1, jobs)
        if burst < 1:
            raise ConfigError("--rate-burst должен быть >= 1")

        return cls(jobs=jobs, rate_limit_per_second=rate, burst=burst)


__all__ = ["ConcurrencyOptions"]
