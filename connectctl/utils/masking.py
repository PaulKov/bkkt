from __future__ import annotations

import re
from typing import Any, Mapping


_SENSITIVE_KEY_RE = re.compile(
    r"(?i)(password|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|bearer|oauth|sasl\.jaas\.config|ssl\..*(password|key|keystore|truststore))"
)


def is_sensitive_key(key: str) -> bool:
    """Вернуть True, если ключ похож на секрет.

    Используется в user-facing выводе (render/explain/diff), чтобы по умолчанию
    не печатать пароли/токены.

    Примечание: это эвристика по имени ключа. Мы не можем надёжно определить,
    что конкретное значение является секретом, если ключ не говорит об этом.
    """

    return bool(_SENSITIVE_KEY_RE.search(key or ""))


def mask_secrets_in_obj(obj: Any, *, mask: str = "***") -> Any:
    """Рекурсивно замаскировать секреты в dict/list.

    Правило:
    - если ключ mapping является "sensitive" → значение заменяется на mask
    - иначе спускаемся рекурсивно
    """

    if isinstance(obj, list):
        return [mask_secrets_in_obj(v, mask=mask) for v in obj]

    if isinstance(obj, Mapping):
        out = {}
        for k, v in obj.items():
            ks = str(k)
            if is_sensitive_key(ks):
                out[k] = mask
            else:
                out[k] = mask_secrets_in_obj(v, mask=mask)
        return out

    return obj
