from __future__ import annotations

from typing import Optional

from ..models import ConnectorType, Environment
from .layout_models import DetectedLayout


_RESERVED_AFTER_CDC = {"dbt"}


def _is_env_token(tok: str) -> bool:
    return tok in {"dev", "stage", "prod"}


def autodetect_layout_from_name(name: str) -> Optional[DetectedLayout]:
    """Autodetect repo layout from connector name.

    Supported patterns (dot-style names):

      <env>.<domain>.<dataset>.source.<system>.<...>.<index>
      <env>.<domain>.<dataset>.sink.<layer>.<system>.(cdc.)?(<kind>.)?....<index>

    For sinks, kind is inferred from the segment after `cdc` when present and
    not in reserved words (e.g. "dbt"), otherwise defaults to "default".

    Returns None if the name does not match the expected conventions.
    """
    if not name or "." not in name:
        return None
    parts = [p for p in name.split(".") if p]
    if len(parts) < 6:
        return None
    if not _is_env_token(parts[0]):
        return None

    try:
        env = Environment.from_str(parts[0])
    except Exception:
        return None

    # Strict convention: env.domain.dataset.(source|sink)...
    domain = parts[1]
    dataset = parts[2]
    kind = "default"

    t = parts[3]
    if t == "source":
        if len(parts) < 6:
            return None
        system = parts[4]
        # connector_dir: connector_<domain>__<dataset>__<rest-without-index>
        rest = parts[5:]
        # Strip trailing index token (either numeric or a placeholder like ${index})
        if rest and (rest[-1].isdigit() or rest[-1] == "${index}"):
            rest = rest[:-1]
        connector_dir = f"connector_{domain}__{dataset}"
        if rest:
            connector_dir = connector_dir + "__" + "__".join(rest)
        return DetectedLayout(
            env=env,
            domain=domain,
            connector_type=ConnectorType.source,
            system=system,
            connector_dir=connector_dir,
            dataset=dataset,
        )

    if t == "sink":
        if len(parts) < 7:
            return None
        layer = parts[4]
        system = parts[5]
        rest = parts[6:]
        if rest and rest[-1].isdigit():
            rest = rest[:-1]

        # Detect kind (events/flatten/custom) only when explicitly present.
        if rest:
            if "cdc" in rest:
                i = rest.index("cdc")
                if i + 1 < len(rest):
                    cand = rest[i + 1]
                    if cand and not cand.isdigit() and cand not in _RESERVED_AFTER_CDC:
                        kind = cand
            else:
                # Fallback: if the last segment looks like a known kind token.
                cand = rest[-1]
                if cand and not cand.isdigit() and cand in {"events", "flatten"}:
                    kind = cand

        # For non-CDC sinks (no explicit kind token after `cdc`), treat the sink layer
        # (raw/ods) as kind when it is a known one. This allows global types/raw and types/ods
        # to be applied to base Iceberg sinks like: prod.<domain>.<dataset>.sink.ods.iceberg.<index>
        if kind == "default" and ("cdc" not in rest) and layer in {"raw", "ods"}:
            kind = layer

        connector_dir = f"connector_{domain}__{dataset}"
        return DetectedLayout(
            env=env,
            domain=domain,
            connector_type=ConnectorType.sink,
            system=system,
            connector_dir=connector_dir,
            dataset=dataset,
            layer=layer,
            kind=kind,
        )

    return None
