from __future__ import annotations

from typing import List, Optional

from ...exceptions import ConfigError
from ...repo.scanner_regex import match_deployable
from ...services.connector_name_meta import parse_connector_name_meta
from ...naming.hints import (
    extract_dataset_from_connector_dir,
    format_deployable_name_hints,
    suggest_normalized_dot_name,
)


def _extract_layer_from_name(name: str) -> Optional[str]:
    parts = [p for p in str(name or "").split(".") if p]
    if "sink" in parts:
        i = parts.index("sink")
        if i + 1 < len(parts):
            return parts[i + 1]
    return None


def validate_export_name(*, export_name: str, remote_name: str, env, layout) -> None:
    """Validate the *repo* connector name (the one that becomes <name>.json in repo).

    Export is special: we may read remote config using one name (remote_name),
    but store it in repo under another (export_name) using --as-name.

    Validation rules (user-facing):
    - export_name must be a deployable dot-style name (dev/stage/prod prefix + .source./.sink.)
    - export_name should be consistent with placement overrides (type/domain/system)
    - export_name env must match --env (to keep GitOps invariant "env -> cluster")
    """

    errs: List[str] = []

    # 1) deployable filename check (dot-style is standard)
    _m_us, m_dot = match_deployable(f"{export_name}.json")
    if not m_dot:
        errs.append(
            "имя не является deployable dot-style: должно начинаться с dev./stage./prod. "
            "и содержать '.source.' или '.sink.'"
        )

    meta = parse_connector_name_meta(export_name)

    # 2) env invariant
    if meta.env and meta.env.lower() != env.value:
        errs.append(f"env в имени ({meta.env!r}) не соответствует --env {env.value!r}")

    # 3) placement consistency (best-effort)
    if (
        meta.integration_type
        and meta.integration_type.lower() != layout.connector_type.value
    ):
        errs.append(
            f"тип в имени ({meta.integration_type!r}) не соответствует размещению/--type ({layout.connector_type.value!r})"
        )
    if meta.domain and meta.domain != layout.domain:
        errs.append(
            f"domain в имени ({meta.domain!r}) не соответствует размещению domain={layout.domain!r}"
        )
    if meta.system and meta.system != layout.system:
        errs.append(
            f"system в имени ({meta.system!r}) не соответствует размещению system={layout.system!r}"
        )

    if meta.index is None:
        errs.append("в имени отсутствует числовой index (последний сегмент)")

    if not errs:
        return

    dataset = layout.dataset or extract_dataset_from_connector_dir(
        connector_dir=layout.connector_dir, domain=layout.domain
    )
    layer = (
        layout.layer
        or _extract_layer_from_name(export_name)
        or _extract_layer_from_name(remote_name)
    )

    hint_block = format_deployable_name_hints(
        connector_type=layout.connector_type,
        domain=layout.domain,
        system=layout.system,
        dataset=dataset,
        layer=layer,
    )

    suggestions = suggest_normalized_dot_name(
        name=remote_name,
        env=env.value,
        domain=layout.domain,
        dataset=dataset,
        connector_type=layout.connector_type,
        system=layout.system,
    )

    lines: List[str] = [
        "Некорректное имя коннектора для export.",
        f"Remote name (в кластере): {remote_name}",
        f"Repo name (в репозитории): {export_name}",
        "",
        "Причины:",
    ]
    for e in errs:
        lines.append(f"  - {e}")

    if suggestions:
        lines.append("")
        lines.append("Похоже, вы имели в виду (варианты):")
        for s in suggestions[:3]:
            lines.append(f"  - {s}")
        lines.append("")
        lines.append("Можно указать нормализованное имя так:")
        lines.append(f"  bkkt export ... {remote_name} --as-name {suggestions[0]}")

    lines.append("")
    lines.append(hint_block)

    raise ConfigError("\n".join(lines))
