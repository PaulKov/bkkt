"""Best-effort разбор метаданных из имени коннектора.

BKKT придерживается dot-style нейминга (части разделены точками).

Цель этого модуля — не 100% строгий парсер, а практичный инструмент для UX:
- показать в CLI полезные поля (env/domain/dataset/type/system/layer/mode/kind/index)
- помочь отлаживать массовые операции и отчёты

Если имя не соответствует ожидаемому формату — парсер возвращает максимум того,
что можно извлечь, плюс warnings.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


_KNOWN_TYPES = {"source", "sink"}
_MODE_TOKENS = {"cdc", "init", "initial", "initial_only", "streaming"}
_KIND_RESERVED = {"dbt"}  # после cdc могут встречаться служебные токены


@dataclass(frozen=True)
class ConnectorNameMeta:
    name: str
    env: Optional[str] = None
    domain: Optional[str] = None
    dataset: Optional[str] = None
    integration_type: Optional[str] = None  # source|sink
    system: Optional[str] = None
    layer: Optional[str] = None
    source_mode: Optional[str] = None  # init|cdc|...
    sink_kind: Optional[str] = None  # flatten|events|...
    index: Optional[int] = None
    tail: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "env": self.env,
            "domain": self.domain,
            "dataset": self.dataset,
            "integration_type": self.integration_type,
            "system": self.system,
            "layer": self.layer,
            "source_mode": self.source_mode,
            "sink_kind": self.sink_kind,
            "index": self.index,
            "tail": list(self.tail),
            "warnings": list(self.warnings),
        }


def parse_connector_name_meta(name: str) -> ConnectorNameMeta:
    raw = str(name or "")
    parts = [p for p in raw.split(".") if p]
    warnings: list[str] = []

    env: Optional[str] = None
    domain: Optional[str] = None
    dataset: Optional[str] = None
    itype: Optional[str] = None
    system: Optional[str] = None
    layer: Optional[str] = None
    source_mode: Optional[str] = None
    sink_kind: Optional[str] = None
    index: Optional[int] = None
    tail: tuple[str, ...] = ()

    if len(parts) < 4:
        warnings.append(
            "Ожидается минимум 4 сегмента: <env>.<domain>.<dataset>.<source|sink>..."
        )
        return ConnectorNameMeta(name=raw, tail=tuple(parts), warnings=tuple(warnings))

    env, domain, dataset, itype = parts[0], parts[1], parts[2], parts[3]
    if itype not in _KNOWN_TYPES:
        warnings.append(
            f"Неожиданный integration_type={itype!r} (ожидалось source|sink)"
        )

    rest = parts[4:]

    # common: index = last token if digit
    if rest and rest[-1].isdigit():
        try:
            index = int(rest[-1])
            rest = rest[:-1]
        except Exception:
            index = None

    if itype == "source":
        if rest:
            system = rest[0]
            tail = tuple(rest[1:])
        else:
            tail = ()
            warnings.append("Для source ожидается хотя бы system после 'source'")

        # mode is a token in tail
        for t in tail:
            tt = t.lower()
            if tt in _MODE_TOKENS:
                source_mode = (
                    "init" if tt in {"init", "initial", "initial_only"} else tt
                )
                break

    elif itype == "sink":
        if len(rest) >= 2:
            layer = rest[0]
            system = rest[1]
            tail = tuple(rest[2:])
        else:
            tail = tuple(rest)
            warnings.append("Для sink ожидается формат: sink.<layer>.<system>...")

        # kind обычно стоит после '.cdc.'
        try:
            i = [t.lower() for t in tail].index("cdc")
            if i + 1 < len(tail):
                candidate = tail[i + 1]
                if candidate.lower() not in _KIND_RESERVED and not candidate.isdigit():
                    sink_kind = candidate
        except ValueError:
            sink_kind = None
        except Exception:
            sink_kind = None

    else:
        # Unknown type, still keep tail.
        tail = tuple(rest)

    return ConnectorNameMeta(
        name=raw,
        env=env,
        domain=domain,
        dataset=dataset,
        integration_type=itype,
        system=system,
        layer=layer,
        source_mode=source_mode,
        sink_kind=sink_kind,
        index=index,
        tail=tail,
        warnings=tuple(warnings),
    )


__all__ = ["ConnectorNameMeta", "parse_connector_name_meta"]
