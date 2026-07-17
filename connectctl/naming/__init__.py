"""Утилиты нейминга коннекторов и манифестов.

Здесь живут чистые (side‑effect free) функции, которые:
- формируют подсказки/примеры для пользователя;
- помогают валидировать dot‑style имена;
- используются и в repo‑сканере, и в командах (export/validate и т.п.).
"""

from .hints import (
    DOT_STYLE_HINT_HEADER,
    extract_dataset_from_connector_dir,
    format_deployable_name_hints,
    guess_env_from_parts,
    suggest_normalized_dot_name,
)

__all__ = [
    "DOT_STYLE_HINT_HEADER",
    "extract_dataset_from_connector_dir",
    "format_deployable_name_hints",
    "guess_env_from_parts",
    "suggest_normalized_dot_name",
]
