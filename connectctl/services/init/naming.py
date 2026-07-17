from __future__ import annotations

from typing import Optional


def build_connector_name(
    *,
    env: str,
    domain: str,
    connector_type: str,
    system: str,
    connector_dir: str,
    dataset: str,
    layer: str,
    index: int,
    mode: Optional[str],
    kind: Optional[str],
    explicit_name: Optional[str],
    name_template: Optional[str],
) -> str:
    """Build connector name for init scaffolding.

    Naming is dot-style by default.

    - source:  <env>.<domain>.<dataset>.source.<system>.(<mode>.)?<index>
    - sink:    <env>.<domain>.<dataset>.sink.<layer>.<system>.(cdc.<kind>.)?<index>

    Users may override using --name or --name-template.
    """

    ctx = {
        "env": env,
        "domain": domain,
        "type": connector_type,
        "system": system,
        "connector_dir": connector_dir,
        "dataset": dataset or "CHANGE_ME",
        "layer": layer or "raw",
        "index": str(index),
        "mode": mode or "",
        "kind": kind or "",
    }

    if name_template:
        return str(name_template).format(**ctx)

    if explicit_name:
        raw = str(explicit_name)
        return raw.format(**ctx) if "{" in raw else raw

    if connector_type == "source":
        if mode:
            return (
                f"{env}.{domain}.{ctx['dataset']}.source.{system}.{mode}.{ctx['index']}"
            )
        return f"{env}.{domain}.{ctx['dataset']}.source.{system}.{ctx['index']}"

    # sink
    if kind:
        return f"{env}.{domain}.{ctx['dataset']}.sink.{ctx['layer']}.{system}.cdc.{kind}.{ctx['index']}"
    return (
        f"{env}.{domain}.{ctx['dataset']}.sink.{ctx['layer']}.{system}.{ctx['index']}"
    )
