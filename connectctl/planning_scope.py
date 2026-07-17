from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import ConnectorPathInfo, ConnectorType, Environment


@dataclass(frozen=True)
class OverrideScope:
    """Ограничение области влияния override-файла."""

    domain: str | None = None
    connector_type: ConnectorType | None = None
    system: str | None = None
    connector_dir: str | None = None
    variant: str | None = None
    mode: str | None = None
    env: Environment | None = None


def infer_override_scope(relpath: Path) -> OverrideScope:
    """Инференс области влияния override-файла.

    Поддерживает специальные поддиректории репозитория:
    - `types/<kind>/...` (sink variants)
    - `modes/<mode>/...` (init/cdc overlays)

    Важно: функция должна работать даже если файл удалён.
    """

    parts = list(relpath.parts)
    fname = relpath.name

    env_restrict: Environment | None = None
    if fname in {"dev.json", "stage.json", "prod.json"}:
        env_restrict = Environment.from_str(fname.replace(".json", ""))

    scope = OverrideScope(env=env_restrict)

    if not parts:
        return scope

    # Helper: scan `types/<kind>` and `modes/<mode>` segments.
    variant: str | None = None
    mode: str | None = None

    if "types" in parts:
        ti = parts.index("types")
        if len(parts) > ti + 1 and not parts[ti + 1].endswith(".json"):
            kind = parts[ti + 1]
            if kind != "default":
                variant = kind

    if "modes" in parts:
        mi = parts.index("modes")
        if len(parts) > mi + 1 and not parts[mi + 1].endswith(".json"):
            mode = parts[mi + 1]

    if parts[0] == "__global":
        # __global/(source|sink)?/(<system>/)?...
        g_ctype = (
            ConnectorType.from_str(parts[1])
            if len(parts) >= 2 and parts[1] in {"source", "sink"}
            else None
        )
        g_system = (
            parts[2] if len(parts) >= 3 and not parts[2].endswith(".json") else None
        )
        return OverrideScope(
            domain=None,
            connector_type=g_ctype,
            system=g_system,
            connector_dir=None,
            variant=variant,
            mode=mode,
            env=env_restrict,
        )

    # Domain-level override: <domain>/.../<file>
    domain = parts[0]
    idx = 1

    ctype: ConnectorType | None = None
    system: str | None = None
    connector_dir: str | None = None

    if len(parts) > idx and parts[idx] in {"source", "sink"}:
        ctype = ConnectorType.from_str(parts[idx])
        idx += 1

    if len(parts) > idx and not parts[idx].endswith(".json"):
        system = parts[idx]
        idx += 1

    # Optional connector_dir, but avoid treating special dirs as connector_dir
    if (
        len(parts) > idx
        and not parts[idx].endswith(".json")
        and parts[idx] not in {"types", "modes"}
    ):
        connector_dir = parts[idx]

    return OverrideScope(
        domain=domain,
        connector_type=ctype,
        system=system,
        connector_dir=connector_dir,
        variant=variant,
        mode=mode,
        env=env_restrict,
    )


def scope_matches(
    info: ConnectorPathInfo, env: Environment, scope: OverrideScope
) -> bool:
    """Проверить, что connector попадает под область влияния override."""

    if env != info.env:
        return False
    if scope.env is not None and scope.env != env:
        return False
    if scope.domain and scope.domain != info.domain:
        return False
    if scope.connector_type and scope.connector_type != info.connector_type:
        return False
    if scope.system and scope.system != info.system:
        return False
    if scope.connector_dir and scope.connector_dir != info.connector_dir:
        return False
    if scope.variant is not None and scope.variant != info.variant:
        return False
    if scope.mode is not None and scope.mode != info.mode:
        return False
    return True
