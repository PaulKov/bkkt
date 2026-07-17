from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

from ..models import ConnectorType


ENV_TOKENS = ("dev", "stage", "prod")


DOT_STYLE_HINT_HEADER = (
    "Стандарт BKKT: **dot-style**. Deployable манифесты должны начинаться с окружения "
    "(dev/stage/prod) и содержать '.source.' или '.sink.' в имени файла."
)


def guess_env_from_parts(parts: Iterable[str]) -> Optional[str]:
    """Best-effort: найти env token (dev|stage|prod) в списке сегментов имени."""

    for p in parts:
        pp = str(p).strip().lower()
        if pp in ENV_TOKENS:
            return pp
    return None


def extract_dataset_from_connector_dir(
    *, connector_dir: str, domain: Optional[str] = None
) -> Optional[str]:
    """Достать dataset из connector_dir.

    Ожидаемый формат:
      connector_<domain>__<dataset>{__<optional_suffix>}
    """

    if not connector_dir:
        return None
    s = str(connector_dir).strip()
    if not s.startswith("connector_"):
        return None

    # If domain is known, prefer strict prefix.
    if domain:
        prefix = f"connector_{domain}__"
        if s.startswith(prefix):
            remainder = s[len(prefix) :]
            dataset = remainder.split("__", 1)[0]
            return dataset or None

    # Generic fallback: connector_<something>__<dataset>...
    m = re.match(r"^connector_[^_]+__([^_]+)(?:__.+)?$", s)
    if not m:
        return None
    dataset = m.group(1)
    return dataset or None


@dataclass(frozen=True)
class NameHints:
    """Пользовательские подсказки по корректному неймингу."""

    templates: List[str]
    examples: List[str]
    notes: List[str]


def _source_template() -> str:
    # mode обычно cdc/init; индекс — последний сегмент.
    return "<env>.<domain>.<dataset>.source.<system>.<mode>.<index>"


def _sink_template() -> str:
    # kind может отсутствовать, но для CDC sinks чаще используется явный токен после cdc.
    return "<env>.<domain>.<dataset>.sink.<layer>.<system>[.cdc.<kind>].<index>"


def _source_example(
    *, env: str, domain: str, dataset: str, system: str, mode: str, index: str
) -> str:
    return f"{env}.{domain}.{dataset}.source.{system}.{mode}.{index}"


def _sink_example(
    *,
    env: str,
    domain: str,
    dataset: str,
    layer: str,
    system: str,
    kind: str,
    index: str,
    include_cdc_kind: bool,
) -> str:
    base = f"{env}.{domain}.{dataset}.sink.{layer}.{system}"
    if include_cdc_kind:
        base += f".cdc.{kind}"
    return f"{base}.{index}"


def build_name_hints(
    *,
    connector_type: Optional[ConnectorType],
    domain: str,
    system: str,
    dataset: Optional[str] = None,
    layer: Optional[str] = None,
    mode: str = "cdc",
    kind: str = "events",
    index: str = "0",
) -> NameHints:
    """Сформировать шаблоны и примеры имён (без env, env перечисляем ниже)."""

    ds = dataset or "<dataset>"
    lay = layer or "raw"

    templates: List[str] = []
    examples: List[str] = []
    notes: List[str] = []

    if connector_type is None or connector_type == ConnectorType.source:
        templates.append(_source_template())
        examples.append(
            _source_example(
                env="dev",
                domain=domain,
                dataset=ds,
                system=system,
                mode=mode,
                index=index,
            )
        )
        examples.append(
            _source_example(
                env="prod",
                domain=domain,
                dataset=ds,
                system=system,
                mode="init",
                index=index,
            )
        )

    if connector_type is None or connector_type == ConnectorType.sink:
        templates.append(_sink_template())
        examples.append(
            _sink_example(
                env="dev",
                domain=domain,
                dataset=ds,
                layer=lay,
                system=system,
                kind=kind,
                index=index,
                include_cdc_kind=True,
            )
        )
        examples.append(
            _sink_example(
                env="prod",
                domain=domain,
                dataset=ds,
                layer=lay,
                system=system,
                kind=kind,
                index=index,
                include_cdc_kind=False,
            )
        )
        notes.append(
            "Для sink (CDC) рекомендуется явный kind после '.cdc.' (например events/flatten), "
            "но некоторые базовые sinks могут быть без него."
        )

    return NameHints(templates=templates, examples=examples, notes=notes)


def format_deployable_name_hints(
    *,
    connector_type: Optional[ConnectorType],
    domain: str,
    system: str,
    dataset: Optional[str] = None,
    layer: Optional[str] = None,
) -> str:
    """Вернуть человеко‑читаемую подсказку по корректному имени."""

    hints = build_name_hints(
        connector_type=connector_type,
        domain=domain,
        system=system,
        dataset=dataset,
        layer=layer,
    )

    lines: List[str] = [DOT_STYLE_HINT_HEADER, "", "Ожидаемые шаблоны имени:"]
    for t in hints.templates:
        lines.append(f"  - {t}")
    lines.append("")
    lines.append("Примеры:")
    for ex in hints.examples:
        lines.append(f"  - {ex}")
    if hints.notes:
        lines.append("")
        lines.append("Примечания:")
        for n in hints.notes:
            lines.append(f"  - {n}")
    return "\n".join(lines)


def suggest_normalized_dot_name(
    *,
    name: str,
    env: str,
    domain: Optional[str] = None,
    dataset: Optional[str] = None,
    connector_type: Optional[ConnectorType] = None,
    system: Optional[str] = None,
) -> List[str]:
    """Best-effort suggestions for turning a non-standard name into a BKKT dot-style name.

    This is intentionally conservative: it only suggests names when we can extract
    an env token somewhere inside the name.
    """

    raw = str(name or "").strip()
    if not raw or "." not in raw:
        return []

    parts = [p for p in raw.split(".") if p]
    env_pos = None
    for i, p in enumerate(parts):
        if p.lower() in ENV_TOKENS:
            env_pos = i
            break
    if env_pos is None:
        return []

    # 1) Remove prefix before env token.
    cand_parts = parts[env_pos:]
    if not cand_parts:
        return []

    # 2) Enforce desired env.
    cand_parts[0] = env

    # 3) Try to enforce known domain/dataset/ctype/system at canonical positions.
    # Canonical: env.domain.dataset.(source|sink)...
    if domain and len(cand_parts) >= 2:
        cand_parts[1] = domain
    if dataset and len(cand_parts) >= 3:
        cand_parts[2] = dataset
    if connector_type and len(cand_parts) >= 4:
        cand_parts[3] = connector_type.value

    # system position differs for source/sink.
    if system and connector_type:
        if connector_type == ConnectorType.source and len(cand_parts) >= 5:
            cand_parts[4] = system
        if connector_type == ConnectorType.sink and len(cand_parts) >= 6:
            # env.domain.dataset.sink.layer.system...
            cand_parts[5] = system

    cand = ".".join(cand_parts)
    # Avoid suggesting the same name.
    if cand == raw:
        return []
    return [cand]
