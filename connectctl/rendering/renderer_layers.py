from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..exceptions import RenderError
from ..lifecycle import ConnectorLifecycle, LifecycleEvaluator
from ..ports import FileSystem
from ..utils import deep_merge, flatten_dict
from .config_merge import merge_config_with_deletes
from .json_loader import load_json_file, normalize_fragment
from .unset_config import (
    BKKT_META_KEY,
    UNSET_CONFIG_KEYS_KEY,
    apply_unset_config_keys,
    normalize_unset_config_keys,
)


@dataclass
class LayerMergeResult:
    name: Optional[str]
    config: Dict[str, Any]

    # Provenance for config leaf keys (flattened dot-keys)
    config_sources: Dict[str, str]
    # Full chain of overrides for config leaf keys (low -> high priority)
    config_sources_chain: Dict[str, Tuple[str, ...]]

    vars_ctx: Dict[str, Any]
    vars_sources: Dict[str, str]

    # Tool meta (not sent to Kafka Connect)
    connectctl_meta: Dict[str, Any]
    connectctl_sources: Dict[str, str]

    # Explicit config-key removals (not sent to Kafka Connect)
    unset_config_keys: Tuple[str, ...]
    unset_config_key_sources: Dict[str, Tuple[str, ...]]

    # Tags are additive across layers
    tags: List[str]
    tags_sources: List[Tuple[str, str]]
    lifecycle: ConnectorLifecycle

    name_first_set_by: Optional[Path]
    name_last_set_by: Optional[Path]


def merge_layer_fragments(
    layer_paths: Sequence[Path], *, repo_root: Path, fs: FileSystem | None = None
) -> LayerMergeResult:
    """Load all layer fragments, normalize and merge them into a single logical manifest.

    Важные правила:
    - `connectctl` (meta) мерджится (deep merge).
    - `connectctl.tags` — *additive* (конкатенация), чтобы теги можно было добавлять слоями.
    - Для explain/debug мы трекаем provenance:
      - vars_sources: для vars.* ключей
      - connectctl_sources: для connectctl.* ключей
      - tags_sources: для каждого добавленного тега
    """

    name: Optional[str] = None
    config: Dict[str, Any] = {}
    config_sources: Dict[str, str] = {}
    config_sources_chain: Dict[str, List[str]] = {}
    vars_ctx: Dict[str, Any] = {}
    vars_sources: Dict[str, str] = {}

    connectctl_meta: Dict[str, Any] = {}
    connectctl_sources: Dict[str, str] = {}
    unset_config_keys: List[str] = []
    unset_config_key_sources: Dict[str, List[str]] = {}

    tags: List[str] = []
    tags_sources: List[Tuple[str, str]] = []
    lifecycle_evaluator = LifecycleEvaluator()

    name_first_set_by: Optional[Path] = None
    name_last_set_by: Optional[Path] = None

    repo_root_resolved = repo_root.resolve()

    for lp in layer_paths:
        obj = load_json_file(lp, fs=fs)
        frag = normalize_fragment(obj)

        try:
            rel_lp = lp.resolve().relative_to(repo_root_resolved).as_posix()
        except Exception:
            rel_lp = str(lp)

        if "vars" in frag:
            if not isinstance(frag["vars"], Mapping):
                raise RenderError(f"vars must be an object in {lp}")
            v = dict(frag["vars"])
            vars_ctx = deep_merge(vars_ctx, v)

            for k in flatten_dict(v).keys():
                vars_sources[k] = f"vars:{rel_lp}"

        if "name" in frag and frag["name"]:
            if name_first_set_by is None:
                name_first_set_by = lp
            name_last_set_by = lp
            name = str(frag["name"])

        if "config" in frag and frag["config"]:
            if not isinstance(frag["config"], Mapping):
                raise RenderError(f"config must be an object in {lp}")
            cfg = dict(frag["config"])
            config = merge_config_with_deletes(config, cfg)

            # Track leaf-key provenance for explain/debug.
            for k, v in flatten_dict(cfg).items():
                if v is None:
                    continue
                src = f"config:{rel_lp}"
                config_sources[k] = src
                config_sources_chain.setdefault(k, []).append(src)

            current_keys = set(flatten_dict(config).keys())
            config_sources = {
                k: v for k, v in config_sources.items() if k in current_keys
            }
            config_sources_chain = {
                k: v for k, v in config_sources_chain.items() if k in current_keys
            }

        if BKKT_META_KEY in frag and frag[BKKT_META_KEY]:
            if not isinstance(frag[BKKT_META_KEY], Mapping):
                raise RenderError(f"bkkt must be an object in {lp}")
            bkkt = dict(frag[BKKT_META_KEY])
            layer_unsets = normalize_unset_config_keys(
                bkkt.get(UNSET_CONFIG_KEYS_KEY),
                source=f"bkkt.{UNSET_CONFIG_KEYS_KEY}:{rel_lp}",
            )
            if layer_unsets:
                config = apply_unset_config_keys(config, layer_unsets)
                for key in layer_unsets:
                    if key not in unset_config_keys:
                        unset_config_keys.append(key)
                    unset_config_key_sources.setdefault(key, []).append(
                        f"bkkt.{UNSET_CONFIG_KEYS_KEY}:{rel_lp}"
                    )
                    config_sources.pop(key, None)
                    config_sources_chain.pop(key, None)

        if "connectctl" in frag and frag["connectctl"]:
            if not isinstance(frag["connectctl"], Mapping):
                raise RenderError(f"connectctl must be an object in {lp}")
            cc = dict(frag["connectctl"])

            tv = cc.pop("tags", None)
            if tv is not None:
                if isinstance(tv, str):
                    tv = [tv]
                if not isinstance(tv, (list, tuple)):
                    raise RenderError(
                        f"connectctl.tags must be a string or list in {lp}"
                    )
                for t in tv:
                    s = str(t).strip()
                    if s:
                        tags.append(s)
                        tags_sources.append((s, f"connectctl.tags:{rel_lp}"))

            if cc:
                lifecycle_evaluator.apply(cc.get("lifecycle"), rel_source=rel_lp)
                connectctl_meta = deep_merge(connectctl_meta, cc)

                for k in flatten_dict(cc).keys():
                    connectctl_sources[k] = f"connectctl:{rel_lp}"

    lifecycle_eval = lifecycle_evaluator.build()
    if lifecycle_eval.connectctl_meta:
        connectctl_meta = deep_merge(connectctl_meta, lifecycle_eval.connectctl_meta)
        connectctl_sources.update(lifecycle_eval.connectctl_sources)

    return LayerMergeResult(
        name=name,
        config=config,
        config_sources=config_sources,
        config_sources_chain={k: tuple(v) for k, v in config_sources_chain.items()},
        vars_ctx=vars_ctx,
        vars_sources=vars_sources,
        connectctl_meta=connectctl_meta,
        connectctl_sources=connectctl_sources,
        unset_config_keys=tuple(unset_config_keys),
        unset_config_key_sources={
            k: tuple(v) for k, v in unset_config_key_sources.items()
        },
        tags=tags,
        tags_sources=tags_sources,
        lifecycle=lifecycle_eval.lifecycle,
        name_first_set_by=name_first_set_by,
        name_last_set_by=name_last_set_by,
    )
