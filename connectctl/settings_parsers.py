from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from .config_models import (
    DirectPutConfig,
    ExportConfig,
    NamingConfig,
    NamingRule,
    PrunePolicy,
    SafetyConfig,
    SyncConfig,
)
from .exceptions import ConfigError
from .settings_models import TagSettings


def as_tuple_str(x: Any) -> Tuple[str, ...]:
    """Унифицированно привести YAML/JSON значение к Tuple[str, ...]."""

    if x is None:
        return ()
    if isinstance(x, str):
        x = [x]
    if isinstance(x, (list, tuple)):
        return tuple(str(i) for i in x if str(i).strip())
    return (str(x),)


def parse_naming(naming_obj: Any) -> NamingConfig:
    if not isinstance(naming_obj, Mapping):
        return NamingConfig()

    enabled = bool(naming_obj.get("enabled", True))
    strict = bool(naming_obj.get("strict", True))

    extra_allowed = as_tuple_str(
        naming_obj.get("extra_allowed") or naming_obj.get("extra_allowed_patterns")
    )

    rules_raw = naming_obj.get("rules") or []
    rules: list[NamingRule] = []

    if isinstance(rules_raw, Mapping):
        # allow mapping form: id -> {template/regex,...}
        for rid, robj in rules_raw.items():
            if not isinstance(robj, Mapping):
                continue
            rules.append(parse_naming_rule(str(rid), robj))

    elif isinstance(rules_raw, list):
        for i, robj in enumerate(rules_raw):
            if not isinstance(robj, Mapping):
                continue
            rid = str(robj.get("id") or f"rule_{i}")
            rules.append(parse_naming_rule(rid, robj))

    return NamingConfig(
        enabled=enabled,
        strict=strict,
        rules=tuple(rules),
        extra_allowed_patterns=extra_allowed,
    )


def parse_naming_rule(rule_id: str, robj: Mapping[str, Any]) -> NamingRule:
    template = robj.get("template")
    regex = robj.get("regex") or robj.get("pattern")
    desc = str(robj.get("description") or "")

    applies_to_raw = robj.get("applies_to") or {}
    applies_to: dict[str, Tuple[str, ...]] = {}
    if isinstance(applies_to_raw, Mapping):
        for k, v in applies_to_raw.items():
            applies_to[str(k)] = as_tuple_str(v)

    return NamingRule(
        id=str(rule_id),
        template=str(template) if template is not None else None,
        regex=str(regex) if regex is not None else None,
        description=desc,
        applies_to=applies_to,
    )


def parse_sync(sync_obj: Any) -> SyncConfig:
    if not isinstance(sync_obj, Mapping):
        return SyncConfig()

    prune_obj = sync_obj.get("prune", {}) or {}
    if not isinstance(prune_obj, Mapping):
        return SyncConfig()

    allow_names = as_tuple_str(prune_obj.get("allow_names") or prune_obj.get("allow"))
    deny_names = as_tuple_str(prune_obj.get("deny_names") or prune_obj.get("deny"))

    allow_regex = as_tuple_str(
        prune_obj.get("allow_regex") or prune_obj.get("allow_patterns")
    )
    deny_regex = as_tuple_str(
        prune_obj.get("deny_regex")
        or prune_obj.get("deny_patterns")
        or prune_obj.get("keep_regex")
        or prune_obj.get("keep_patterns")
    )

    return SyncConfig(
        prune=PrunePolicy(
            allow_names=allow_names,
            deny_names=deny_names,
            allow_regex=allow_regex,
            deny_regex=deny_regex,
        )
    )


def parse_safety(safety_obj: Any) -> SafetyConfig:
    """Parse optional safety/permissions configuration."""

    if not isinstance(safety_obj, Mapping):
        return SafetyConfig()

    dp_defaults = DirectPutConfig()
    dp_obj = safety_obj.get("direct_put") or safety_obj.get("put_config") or {}
    if not isinstance(dp_obj, Mapping):
        return SafetyConfig()

    enabled = bool(dp_obj.get("enabled", dp_defaults.enabled))

    allowed_envs = as_tuple_str(
        dp_obj.get("allowed_envs") or dp_obj.get("envs") or dp_obj.get("allow_envs")
    )
    if not allowed_envs:
        allowed_envs = dp_defaults.allowed_envs

    require_existing = bool(
        dp_obj.get("require_existing", dp_defaults.require_existing)
    )
    allow_create = bool(dp_obj.get("allow_create", dp_defaults.allow_create))

    return SafetyConfig(
        direct_put=DirectPutConfig(
            enabled=enabled,
            allowed_envs=allowed_envs,
            require_existing=require_existing,
            allow_create=allow_create,
        )
    )


def parse_export(export_obj: Any) -> ExportConfig:
    """Parse optional export configuration."""

    if not isinstance(export_obj, Mapping):
        return ExportConfig()

    auto_suffix = export_obj.get(
        "auto_index_suffix_on_collision", export_obj.get("auto_index_suffix", True)
    )
    return ExportConfig(auto_index_suffix_on_collision=bool(auto_suffix))


def parse_tags(tags_obj: Any) -> TagSettings:
    """Parse optional tag configuration.

    Expected structure in connectctl.yaml:

    tags:
      hard_conflict_params: ["cluster"]
      definitions:
        external:
          cluster: external_basic
        team_a:
          some_param: 1
    """

    if not isinstance(tags_obj, Mapping):
        return TagSettings()

    hard = (
        tags_obj.get("hard_conflict_params")
        or tags_obj.get("hard_conflicts")
        or ("cluster",)
    )
    hard_conflict_params = as_tuple_str(hard) or ("cluster",)

    defs_obj = tags_obj.get("definitions") or tags_obj.get("defs") or {}
    definitions: Dict[str, Dict[str, Any]] = {}
    if isinstance(defs_obj, Mapping):
        for tag, cfg in defs_obj.items():
            if cfg is None:
                definitions[str(tag)] = {}
                continue
            if not isinstance(cfg, Mapping):
                raise ConfigError(f"tags.definitions.{tag} must be a mapping")
            definitions[str(tag)] = dict(cfg)

    return TagSettings(
        definitions=definitions, hard_conflict_params=hard_conflict_params
    )
