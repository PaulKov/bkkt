from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from ...validation.repo_layout_models import CONNECTOR_DIR_DATASET_RE


@dataclass(frozen=True)
class ParsedConnectorDir:
    domain_part: str
    dataset: str
    suffix: str  # includes leading '__' if present, or ''


_FULL_PREFIX = "connector_"


def _sanitize_token(value: str) -> str:
    """Convert arbitrary string to a recommended token for <dataset>.

    Rules:
    - keep letters/digits/underscore
    - everything else becomes underscore
    - collapse consecutive underscores
    - strip leading/trailing underscores

    Returns empty string if nothing meaningful remains.
    """

    v = value.strip()
    if not v:
        return ""
    v = re.sub(r"[^a-zA-Z0-9_]+", "_", v)
    v = re.sub(r"_+", "_", v)
    v = v.strip("_")
    return v


def parse_connector_dir_name(name: str) -> Optional[ParsedConnectorDir]:
    """Parse connector_dir name into (domain_part, dataset, suffix).

    Expected base format:
        connector_<domain>__<dataset>{__<optional_suffix>}

    We keep suffix as-is (including the leading '__').
    """

    if not name.startswith(_FULL_PREFIX):
        return None
    rest = name[len(_FULL_PREFIX) :]
    if "__" not in rest:
        return None
    domain_part, after = rest.split("__", 1)
    if not domain_part:
        return None
    if not after or after.startswith("__"):
        return None
    if "__" in after:
        dataset, tail = after.split("__", 1)
        suffix = "__" + tail if tail else ""
    else:
        dataset, suffix = after, ""
    return ParsedConnectorDir(domain_part=domain_part, dataset=dataset, suffix=suffix)


def is_valid_connector_dir(expected_domain: str, name: str) -> bool:
    parsed = parse_connector_dir_name(name)
    if not parsed:
        return False
    if parsed.domain_part != expected_domain:
        return False
    if not parsed.dataset or not CONNECTOR_DIR_DATASET_RE.match(parsed.dataset):
        return False
    return True


def suggest_connector_dir_name(
    expected_domain: str, name: str
) -> Tuple[Optional[str], str, bool]:
    """Suggest a normalized connector_dir name.

    Returns:
        (suggested_name|None, reason, manual)

    manual=True means we could not build a safe suggestion automatically.
    """

    if is_valid_connector_dir(expected_domain, name):
        return None, "", False

    reasons: list[str] = []

    if not name.startswith(_FULL_PREFIX):
        ds = _sanitize_token(name)
        if not ds:
            return (
                None,
                "Невозможно вывести <dataset> из имени каталога (пустое/некорректное).",
                True,
            )
        return (
            f"connector_{expected_domain}__{ds}",
            "Каталог не начинается с 'connector_'.",
            False,
        )

    parsed = parse_connector_dir_name(name)
    if parsed:
        if parsed.domain_part != expected_domain:
            reasons.append(
                f"Домен в имени '{parsed.domain_part}' не совпадает с каталогом домена '{expected_domain}'."
            )
        dataset = parsed.dataset
        if not dataset or not CONNECTOR_DIR_DATASET_RE.match(dataset):
            sanitized = _sanitize_token(dataset)
            if not sanitized:
                return (
                    None,
                    "Невозможно нормализовать <dataset> (после очистки пусто).",
                    True,
                )
            reasons.append(
                "Сегмент <dataset> содержит неожиданные символы (нормализовано)."
            )
            dataset = sanitized
        suggested = f"connector_{expected_domain}__{dataset}{parsed.suffix}"
        return (
            suggested,
            "; ".join(reasons) if reasons else "Нормализация имени connector_dir.",
            False,
        )

    # Starts with connector_ but doesn't parse well (no '__' or empty dataset).
    after = name[len(_FULL_PREFIX) :]
    ds = _sanitize_token(after.replace("__", "_"))
    if not ds:
        return (
            None,
            "Невозможно разобрать имя connector_dir (некорректный формат).",
            True,
        )
    return (
        f"connector_{expected_domain}__{ds}",
        "Невозможно разобрать имя connector_dir (попытка нормализации).",
        False,
    )
