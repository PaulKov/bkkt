from __future__ import annotations

import re


_SENSITIVE_KEY_RE = re.compile(
    r"(?i)(password|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|sasl\\.jaas\\.config|ssl\\..*password)"
)


def is_sensitive_var(key: str) -> bool:
    """Return True if a placeholder key is considered sensitive.

    Used only for rendering diagnostics: sensitive values are masked as "***".
    """

    return bool(_SENSITIVE_KEY_RE.search(key or ""))
