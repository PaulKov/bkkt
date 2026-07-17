from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .exceptions import ConfigError
from .models import ClusterLifecycle


_ALL_SELECTORS = {"*", "all"}


@dataclass(frozen=True)
class ClusterLifecycleOverride:
    """Root-level lifecycle override for one cluster/env selector."""

    cluster: str
    env: str
    lifecycle: ClusterLifecycle

    @property
    def specificity(self) -> int:
        cluster_score = 0 if self.cluster in _ALL_SELECTORS else 1
        env_score = 0 if self.env in _ALL_SELECTORS else 1
        return cluster_score + env_score

    def matches(self, *, cluster: str, env: str) -> bool:
        return self._matches(self.cluster, cluster) and self._matches(self.env, env)

    @staticmethod
    def _matches(selector: str, value: str) -> bool:
        return selector in _ALL_SELECTORS or selector == value


def parse_cluster_lifecycle(raw: Any, *, path: str) -> ClusterLifecycle:
    """Parse a lifecycle mapping from connectctl.yaml.

    Empty/missing lifecycle means an enabled scope with no lifecycle metadata.
    When `disabled=true`, a human-readable reason is required so operators see
    why runtime operations are intentionally skipped.
    """

    if raw is None:
        return ClusterLifecycle()
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{path} must be a mapping")

    disabled = _as_bool(raw.get("disabled", False), path=f"{path}.disabled")
    reason = _as_optional_str(raw.get("reason"))
    ticket = _as_optional_str(raw.get("ticket"))
    until = _as_optional_str(raw.get("until"))

    if disabled and not reason:
        raise ConfigError(f"{path}.reason is required when disabled=true")

    return ClusterLifecycle(
        disabled=disabled,
        reason=reason,
        ticket=ticket,
        until=until,
    )


def parse_root_lifecycle_overrides(raw: Any) -> tuple[ClusterLifecycleOverride, ...]:
    """Parse root `cluster_lifecycle.overrides` entries."""

    if raw is None:
        return ()
    if not isinstance(raw, Mapping):
        raise ConfigError("cluster_lifecycle must be a mapping")

    overrides_raw = raw.get("overrides") or ()
    if isinstance(overrides_raw, (str, bytes)) or not isinstance(
        overrides_raw, Sequence
    ):
        raise ConfigError("cluster_lifecycle.overrides must be a list")

    overrides: list[ClusterLifecycleOverride] = []
    for index, item in enumerate(overrides_raw):
        path = f"cluster_lifecycle.overrides[{index}]"
        if not isinstance(item, Mapping):
            raise ConfigError(f"{path} must be a mapping")
        cluster = _selector(item.get("cluster", "all"), path=f"{path}.cluster")
        env = _selector(item.get("env", "all"), path=f"{path}.env")
        overrides.append(
            ClusterLifecycleOverride(
                cluster=cluster,
                env=env,
                lifecycle=parse_cluster_lifecycle(item, path=path),
            )
        )

    return tuple(sorted(overrides, key=lambda item: item.specificity))


def apply_effective_lifecycle(
    env_cfg: Mapping[str, Any],
    *,
    group_lifecycle: ClusterLifecycle,
    root_overrides: Sequence[ClusterLifecycleOverride],
    cluster: str,
    env: str,
) -> dict[str, Any]:
    """Return env config with inherited/effective lifecycle materialized."""

    effective = group_lifecycle.merge(
        parse_cluster_lifecycle(
            env_cfg.get("lifecycle"),
            path=f"clusters.{cluster}.{env}.lifecycle",
        )
    )
    for override in root_overrides:
        if override.matches(cluster=cluster, env=env):
            effective = effective.merge(override.lifecycle)

    resolved = dict(env_cfg)
    if effective.configured:
        resolved["lifecycle"] = effective.to_meta()
    else:
        resolved.pop("lifecycle", None)
    return resolved


def disabled_cluster_message(
    *,
    cluster: str,
    env: str,
    lifecycle: ClusterLifecycle,
) -> str:
    reason = lifecycle.reason or "no reason provided"
    parts = [
        f"Cluster group {cluster!r} env={env} is disabled via cluster lifecycle: {reason}"
    ]
    if lifecycle.ticket:
        parts.append(f"ticket={lifecycle.ticket}")
    if lifecycle.until:
        parts.append(f"until={lifecycle.until}")
    return ". ".join(parts)


def _selector(raw: Any, *, path: str) -> str:
    value = _as_optional_str(raw)
    if not value:
        raise ConfigError(f"{path} must not be empty")
    return value


def _as_optional_str(raw: Any) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _as_bool(raw: Any, *, path: str) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return False
    if isinstance(raw, int) and raw in {0, 1}:
        return bool(raw)
    if isinstance(raw, str):
        value = raw.strip().lower()
        if value in {"1", "true", "yes", "y", "on"}:
            return True
        if value in {"0", "false", "no", "n", "off"}:
            return False
    raise ConfigError(f"{path} must be boolean")


__all__ = [
    "ClusterLifecycleOverride",
    "apply_effective_lifecycle",
    "disabled_cluster_message",
    "parse_cluster_lifecycle",
    "parse_root_lifecycle_overrides",
]
