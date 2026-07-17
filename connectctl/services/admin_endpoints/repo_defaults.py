from __future__ import annotations

from typing import Any, Mapping

from ...app.context import CliContext
from ...models import Environment
from ...rendering.json_loader import load_json_file, normalize_fragment
from ...services.config.raw_clusters import parse_raw_cluster_groups
from ...services.config.raw_loader import load_raw_config
from ...settings_clusters_inheritance import ClusterGroupEnvResolver
from .models import RawAdminScope, RepoAdminDefaults


class RepoAdminDefaultsLoader:
    """Reads admin endpoint defaults from repo render vars."""

    def __init__(self, ctx: CliContext) -> None:
        self.ctx = ctx

    def load(self, env: Environment) -> RepoAdminDefaults:
        path = self.ctx.repo_root / "__global" / f"{env.value}.json"
        if not self.ctx.fs.exists(path):
            return RepoAdminDefaults()
        obj = load_json_file(path, fs=self.ctx.fs)
        frag = normalize_fragment(obj)
        kafka_obj = _kafka_vars(frag)
        if kafka_obj is None:
            return RepoAdminDefaults()
        return RepoAdminDefaults(
            bootstrap_servers=_split_csv(kafka_obj.get("bootstrap_servers")),
            schema_registry_urls=_split_csv(kafka_obj.get("schema_registry_url")),
            source_label=f"__global/{env.value}.json vars",
        )


class RawAdminScopeLoader:
    """Reads raw cluster scope shape before typed parsing drops empty endpoints."""

    def __init__(self, ctx: CliContext) -> None:
        self.ctx = ctx
        self._scopes: dict[tuple[str, Environment], RawAdminScope] | None = None

    def get(self, cluster_group: str, env: Environment) -> RawAdminScope:
        scopes = self._load_scopes()
        return scopes.get((cluster_group, env), RawAdminScope())

    def _load_scopes(self) -> dict[tuple[str, Environment], RawAdminScope]:
        if self._scopes is not None:
            return self._scopes
        raw = load_raw_config(self.ctx.config_path, fs=self.ctx.fs)
        parsed = parse_raw_cluster_groups(raw.data.get("clusters", {}))
        resolver = ClusterGroupEnvResolver(parsed.groups)
        scopes: dict[tuple[str, Environment], RawAdminScope] = {}
        for group, env_map in parsed.groups.items():
            for env in env_map.keys():
                resolved = resolver.resolve_env_mapping(group, env=env)
                scopes[(group, env)] = _raw_scope(resolved)
        self._scopes = scopes
        return scopes


def _raw_scope(value: Any) -> RawAdminScope:
    if not isinstance(value, Mapping):
        return RawAdminScope()
    kafka = value.get("kafka")
    schema_registry = value.get("schema_registry")
    return RawAdminScope(
        kafka=kafka if isinstance(kafka, Mapping) else None,
        schema_registry=(
            schema_registry if isinstance(schema_registry, Mapping) else None
        ),
    )


def _kafka_vars(frag: Mapping[str, Any]) -> Mapping[str, Any] | None:
    vars_obj = frag.get("vars")
    if not isinstance(vars_obj, Mapping):
        return None
    kafka_obj = vars_obj.get("kafka")
    return kafka_obj if isinstance(kafka_obj, Mapping) else None


def _split_csv(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, (list, tuple)):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return ()
