from __future__ import annotations

import re
from typing import Dict, Mapping


def rewrite_iceberg_sink_name_kind(name: str, target_kind: str) -> str:
    """Переписать dot-style имя sink коннектора под нужный kind.

    Пример:
      prod.merchants.acme_common.sink.raw.iceberg.cdc.flatten.dbt.0
        -> kind=events => prod.merchants.acme_common.sink.raw.iceberg.cdc.events.dbt.0

    Если kind="default", то известный kind (events/flatten) после cdc будет удалён (если есть).
    """
    if not name or "." not in name:
        return name
    parts = [p for p in name.split(".") if p]
    if len(parts) < 7 or parts[3] != "sink":
        return name

    # locate cdc segment (if any)
    rest = parts[6:]
    if "cdc" in rest:
        i = rest.index("cdc")
        after = rest[i + 1] if i + 1 < len(rest) else None
        known = {"events", "flatten"}
        if target_kind == "default":
            if after in known:
                del rest[i + 1]
        else:
            if after in known:
                rest[i + 1] = target_kind
            else:
                rest.insert(i + 1, target_kind)
        return ".".join(parts[:6] + rest)

    # no cdc segment: best-effort replace last known kind, otherwise append
    known = {"events", "flatten"}
    if rest and rest[-1] in known:
        if target_kind == "default":
            rest = rest[:-1]
        else:
            rest[-1] = target_kind
    else:
        if target_kind != "default":
            rest.append(target_kind)
    return ".".join(parts[:6] + rest)


def infer_flatten_id_columns_from_remote(
    remote_config: Mapping[str, object]
) -> Dict[str, str]:
    """Best-effort infer per-table id-columns from a flatten connector remote config."""
    out: Dict[str, str] = {}
    for k, v in remote_config.items():
        if not isinstance(k, str):
            continue
        if not k.startswith("iceberg.table."):
            continue
        if not k.endswith(".id-columns"):
            continue
        m = re.match(r"^iceberg\.table\.[^.]+\.([^.]+)\.id-columns$", k)
        if not m:
            continue
        table = m.group(1)
        # Remove known suffixes (best-effort)
        for suf in ("__flatten", "__events"):
            if table.endswith(suf):
                table = table[: -len(suf)]
                break
        out[table] = str(v)
    return out
