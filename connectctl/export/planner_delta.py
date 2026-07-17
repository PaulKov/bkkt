from __future__ import annotations

from typing import Any, Dict, Mapping


def compute_delta_for_remote_keys(
    *,
    rendered_config: Mapping[str, Any],
    remote_config: Mapping[str, Any],
    include_different: bool = True,
) -> Dict[str, Any]:
    """Вычислить env-specific delta, которую нужно записать при `export`.

    По умолчанию (include_different=True) включаем:
      - ключи, отсутствующие в rendered_config
      - ключи, присутствующие, но с другим значением

    Для “минимального” экспорта (include_different=False) включаем только ключи,
    которых нет в rendered_config (рассчитываем на overrides в репо).
    """

    delta: Dict[str, Any] = {}
    for k, v in remote_config.items():
        if k not in rendered_config:
            delta[k] = v
            continue
        if include_different and rendered_config.get(k) != v:
            delta[k] = v
    return delta


def compute_unset_keys_for_absent_remote(
    *,
    rendered_config: Mapping[str, Any],
    remote_config: Mapping[str, Any],
) -> tuple[str, ...]:
    """Keys inherited from overrides but absent in the live connector.

    During export with reuse-overrides these must be represented as explicit
    ``bkkt.unset_config_keys`` metadata rather than ``"config": {"key": null}``.
    """

    return tuple(sorted(str(k) for k in set(rendered_config) - set(remote_config)))
