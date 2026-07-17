from __future__ import annotations

from dataclasses import replace
from fnmatch import fnmatchcase
from typing import Any, Dict, Iterable, Mapping, Tuple

from connectctl.models import ConnectorManifest
from connectctl.rendering.renderer_models import RenderResult


def _norm_patterns(patterns: Iterable[str]) -> Tuple[str, ...]:
    out = []
    for p in patterns:
        if p is None:
            continue
        s = str(p).strip()
        if not s:
            continue
        out.append(s)
    # stable order is important for reproducible logs
    return tuple(out)


def should_prune_key(key: str, patterns: Iterable[str]) -> bool:
    key = str(key)
    for p in _norm_patterns(patterns):
        # fnmatch supports "*" and "?" wildcards and works well with dotted keys.
        if fnmatchcase(key, p):
            return True
    return False


def prune_config(
    config: Mapping[str, Any], patterns: Iterable[str]
) -> Tuple[Dict[str, Any], Tuple[str, ...]]:
    """Remove config keys matching any of the patterns.

    Patterns use shell-style wildcards (fnmatch), for example:
      - iceberg.kafka.*
      - *.schema.registry.url
      - *override.bootstrap.servers
      - bootstrap.servers
    """
    patterns_t = _norm_patterns(patterns)
    if not patterns_t:
        return dict(config), ()

    removed = []
    out: Dict[str, Any] = {}
    for k, v in config.items():
        if should_prune_key(str(k), patterns_t):
            removed.append(str(k))
        else:
            out[str(k)] = v
    removed_sorted = tuple(sorted(set(removed)))
    return out, removed_sorted


def apply_prune_to_manifest(
    manifest: ConnectorManifest, patterns: Iterable[str]
) -> Tuple[ConnectorManifest, Tuple[str, ...]]:
    cfg, removed = prune_config(manifest.config, patterns)
    if not removed:
        return manifest, ()
    # ConnectorManifest is frozen -> replace()
    new_manifest = replace(manifest, config=cfg)
    return new_manifest, removed


def apply_prune_to_render_result(
    rr: RenderResult, patterns: Iterable[str]
) -> Tuple[RenderResult, Tuple[str, ...]]:
    new_manifest, removed = apply_prune_to_manifest(rr.manifest, patterns)
    if not removed:
        return rr, ()
    rr.manifest = new_manifest

    # Keep provenance only for remaining config keys (flat config).
    keep = set(new_manifest.config.keys())
    rr.config_sources = {k: v for k, v in rr.config_sources.items() if k in keep}
    rr.config_sources_chain = {
        k: v for k, v in rr.config_sources_chain.items() if k in keep
    }
    return rr, removed
