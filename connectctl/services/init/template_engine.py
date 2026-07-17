from __future__ import annotations

import fnmatch
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

from ...exceptions import ConfigError
from ...ports import FileSystem
from .models import InitOptions, InitTemplateOverride


@dataclass(frozen=True)
class InitFileTemplateResult:
    """Result of building init JSON for a single output file."""

    out_path: Path
    data: Dict[str, Any]
    template_layers: List[str]
    override_layers: List[str]

    def count_vars(self) -> int:
        return _count_leaf_keys(self.data.get("vars") or {})

    def count_config(self) -> int:
        cfg = self.data.get("config") or {}
        return _count_leaf_keys(cfg) if isinstance(cfg, dict) else 0


def build_all_json(opts: InitOptions, *, log: logging.Logger) -> InitFileTemplateResult:
    """Build content for <connector_dir>/all.json."""
    base = _base_all_template(opts)
    layers = [
        f"built-in (vars={_count_leaf_keys(base.get('vars') or {})}, config={_count_leaf_keys(base.get('config') or {})})"
    ]
    merged = _apply_template_files(
        base, layers, opts, _all_template_candidates(opts), log=log
    )

    # Apply overrides: for source we only allow vars (to keep all.json clean).
    allowed = {"vars"} if opts.connector_type == "source" else {"vars", "config"}
    merged2, ov_layers = _apply_overrides(
        merged,
        opts.template_overrides,
        target_relpath="all.json",
        allowed=allowed,
        log=log,
    )

    return InitFileTemplateResult(
        out_path=opts.target_dir / "all.json",
        data=merged2,
        template_layers=layers,
        override_layers=ov_layers,
    )


def build_env_json(
    opts: InitOptions, env: str, *, log: logging.Logger
) -> InitFileTemplateResult:
    """Build content for <connector_dir>/<env>.json."""
    base = _base_env_template(opts, env)
    layers = [
        f"built-in (vars={_count_leaf_keys(base.get('vars') or {})}, config={_count_leaf_keys(base.get('config') or {})})"
    ]
    merged = _apply_template_files(
        base, layers, opts, _env_template_candidates(opts, env), log=log
    )

    allowed = {"vars", "config"}
    merged2, ov_layers = _apply_overrides(
        merged,
        opts.template_overrides,
        target_relpath=f"{env}.json",
        allowed=allowed,
        log=log,
    )

    return InitFileTemplateResult(
        out_path=opts.target_dir / f"{env}.json",
        data=merged2,
        template_layers=layers,
        override_layers=ov_layers,
    )


def build_mode_all_json(
    opts: InitOptions, mode: str, *, log: logging.Logger
) -> InitFileTemplateResult:
    """Build content for <connector_dir>/modes/<mode>/all.json."""

    base = _base_mode_all_template(opts, mode)
    layers = [
        f"built-in (vars={_count_leaf_keys(base.get('vars') or {})}, config={_count_leaf_keys(base.get('config') or {})})"
    ]
    merged = _apply_template_files(
        base, layers, opts, _mode_all_template_candidates(opts, mode), log=log
    )

    allowed = {"vars", "config"}
    merged2, ov_layers = _apply_overrides(
        merged,
        opts.template_overrides,
        target_relpath=f"modes/{mode}/all.json",
        allowed=allowed,
        log=log,
    )

    # Special UX: --init-only must enforce initial_only for init-mode.
    if opts.init_only and mode == "init":
        patch = {"vars": {"debezium_snapshot_mode_init": "initial_only"}}
        merged2 = _deep_merge(merged2, patch)
        ov_layers.append("flag:--init-only (json, vars=1, config=0)")

    return InitFileTemplateResult(
        out_path=opts.target_dir / "modes" / mode / "all.json",
        data=merged2,
        template_layers=layers,
        override_layers=ov_layers,
    )


def build_mode_env_json(
    opts: InitOptions,
    mode: str,
    env: str,
    *,
    log: logging.Logger,
) -> InitFileTemplateResult:
    """Build content for <connector_dir>/modes/<mode>/<env>.json."""

    base = _base_mode_env_template(opts, mode, env)
    layers = [
        f"built-in (vars={_count_leaf_keys(base.get('vars') or {})}, config={_count_leaf_keys(base.get('config') or {})})"
    ]
    merged = _apply_template_files(
        base, layers, opts, _mode_env_template_candidates(opts, mode, env), log=log
    )

    allowed = {"vars", "config"}
    merged2, ov_layers = _apply_overrides(
        merged,
        opts.template_overrides,
        target_relpath=f"modes/{mode}/{env}.json",
        allowed=allowed,
        log=log,
    )

    return InitFileTemplateResult(
        out_path=opts.target_dir / "modes" / mode / f"{env}.json",
        data=merged2,
        template_layers=layers,
        override_layers=ov_layers,
    )


def build_type_all_json(
    opts: InitOptions, kind: str, *, log: logging.Logger
) -> InitFileTemplateResult:
    """Build content for <connector_dir>/types/<kind>/all.json (sink kinds)."""

    base = _base_type_all_template(opts, kind)
    layers = [
        f"built-in (vars={_count_leaf_keys(base.get('vars') or {})}, config={_count_leaf_keys(base.get('config') or {})})"
    ]
    merged = _apply_template_files(
        base, layers, opts, _type_all_template_candidates(opts, kind), log=log
    )

    allowed = {"vars", "config"}
    merged2, ov_layers = _apply_overrides(
        merged,
        opts.template_overrides,
        target_relpath=f"types/{kind}/all.json",
        allowed=allowed,
        log=log,
    )

    return InitFileTemplateResult(
        out_path=opts.target_dir / "types" / kind / "all.json",
        data=merged2,
        template_layers=layers,
        override_layers=ov_layers,
    )


def build_type_env_json(
    opts: InitOptions,
    kind: str,
    env: str,
    *,
    log: logging.Logger,
) -> InitFileTemplateResult:
    """Build content for <connector_dir>/types/<kind>/<env>.json (sink kinds)."""

    base = _base_type_env_template(opts, kind, env)
    layers = [
        f"built-in (vars={_count_leaf_keys(base.get('vars') or {})}, config={_count_leaf_keys(base.get('config') or {})})"
    ]
    merged = _apply_template_files(
        base, layers, opts, _type_env_template_candidates(opts, kind, env), log=log
    )

    allowed = {"vars", "config"}
    merged2, ov_layers = _apply_overrides(
        merged,
        opts.template_overrides,
        target_relpath=f"types/{kind}/{env}.json",
        allowed=allowed,
        log=log,
    )

    return InitFileTemplateResult(
        out_path=opts.target_dir / "types" / kind / f"{env}.json",
        data=merged2,
        template_layers=layers,
        override_layers=ov_layers,
    )


# ---------------------------
# Base templates
# ---------------------------


def _base_all_template(opts: InitOptions) -> Dict[str, Any]:
    if opts.connector_type == "source":
        return {"vars": {"dataset": opts.dataset}}
    if opts.system == "clickhouse":
        return {
            "config": {
                "connector.class": "com.clickhouse.kafka.connect.ClickHouseSinkConnector",
                "tasks.max": "1",
                "topics": "CHANGE_ME_TOPIC",
                "topic2TableMap": "CHANGE_ME_TOPIC=change_me_raw",
                "key.converter": "org.apache.kafka.connect.storage.StringConverter",
                "key.converter.schemas.enable": "false",
                "value.converter": "org.apache.kafka.connect.json.JsonConverter",
                "value.converter.schemas.enable": "false",
                "errors.log.enable": "true",
                "errors.log.include.messages": "true",
                "behavior.on.parse.error": "log",
                "log.enable": "true",
                "consumer.override.auto.offset.reset": "earliest",
            },
            "vars": {
                "dataset": opts.dataset,
                "layer": opts.layer,
                "index": opts.index,
            },
        }
    # sink (iceberg-oriented default preserved for backward compatibility)
    return {
        "config": {
            # comma-separated list, keep as a single string to match Kafka Connect expectations
            "topics": (
                "cdc.${env}.${domain}.${dataset}.CHANGE_ME_DB.CHANGE_ME_TABLE1.${index},"
                "cdc.${env}.${domain}.${dataset}.CHANGE_ME_DB.CHANGE_ME_TABLE2.${index}"
            )
        },
        "vars": {
            "dataset": opts.dataset,
            "layer": opts.layer,
            "index": opts.index,
            "iceberg": {
                "db_name": "${env}__dbt__${domain}__${dataset}__${layer}",
                "warehouse": "s3://${s3.bucket}/iceberg/lakehouse/dbt/${domain}/${dataset}/${layer}",
            },
        },
    }


def _base_env_template(opts: InitOptions, env: str) -> Dict[str, Any]:
    if opts.connector_type != "source":
        if opts.system == "clickhouse":
            return {
                "vars": {
                    "clickhouse": {
                        "secret": f"{env}/${{domain}}/clickhouse",
                        "database": "CHANGE_ME_DATABASE",
                    }
                },
                "config": {
                    "hostname": "${secretManager:${clickhouse.secret}:host}",
                    "port": "${secretManager:${clickhouse.secret}:port}",
                    "database": "${clickhouse.database}",
                    "username": "${secretManager:${clickhouse.secret}:username}",
                    "password": "${secretManager:${clickhouse.secret}:password}",
                },
            }
        return {"vars": {}, "config": {}}

    # Source (Debezium-like) defaults: placeholders + common best-practice config
    return {
        "vars": {
            "db": {
                "secret": "dbz-${domain}-${env}",
            },
            "index": 0,
        },
        "config": {
            "database.connectionTimeZone": "Europe/Moscow",
            "database.hostname": "${secretManager:${db.secret}:host}",
            "table.include.list": "CHANGE_ME_TABLES_COMMA_SEPARATED_LIST",
            "database.dbname": "${secretManager:${db.secret}:dbname}",
            "database.password": "${secretManager:${db.secret}:password}",
            "database.port": "${secretManager:${db.secret}:port}",
            "database.user": "${secretManager:${db.secret}:username}",
            "datetime.format.timestamp.zone": "Europe/Moscow",
            "snapshot.delay.ms": "5000",
            "topic.creation.default.retention.ms": "286400000",
            "topic.creation.default.segment.ms": "243200000",
            "transforms.replaceTopicName.replacement": "cdc.${env}.${domain}.${dataset}.$1.$2.${index}",
        },
    }


def _base_mode_all_template(opts: InitOptions, mode: str) -> Dict[str, Any]:
    """Built-in template for mode overlay all.json.

    Keep it intentionally minimal. The main goal is to create a "place" for mode overrides.
    """

    # Source: helpful defaults for Debezium snapshot.mode variables.
    if opts.connector_type == "source":
        if mode == "cdc":
            return {"vars": {"debezium_snapshot_mode_cdc": "no_data"}}
        if mode == "init":
            return {"vars": {"debezium_snapshot_mode_init": "initial"}}

    return {"vars": {}, "config": {}}


def _base_mode_env_template(opts: InitOptions, mode: str, env: str) -> Dict[str, Any]:
    # Mode env override is optional; start empty.
    return {"vars": {}, "config": {}}


def _base_type_all_template(opts: InitOptions, kind: str) -> Dict[str, Any]:
    # Sink kind/type overlay: start empty and let __init_templates define real defaults.
    return {"vars": {}, "config": {}}


def _base_type_env_template(opts: InitOptions, kind: str, env: str) -> Dict[str, Any]:
    return {"vars": {}, "config": {}}


# ---------------------------
# Template files (repo overrides)
# ---------------------------


def _all_template_candidates(opts: InitOptions) -> List[Path]:
    d = opts.domain
    c = opts.connector_type
    s = opts.system
    cd = opts.connector_dir
    return [
        Path("__global/all.json"),
        Path(f"__global/{c}/all.json"),
        Path(f"__global/{c}/{s}/all.json"),
        Path(f"{d}/all.json"),
        Path(f"{d}/{c}/all.json"),
        Path(f"{d}/{c}/{s}/all.json"),
        Path(f"{d}/{c}/{s}/{cd}/all.json"),
    ]


def _env_template_candidates(opts: InitOptions, env: str) -> List[Path]:
    d = opts.domain
    c = opts.connector_type
    s = opts.system
    cd = opts.connector_dir
    return [
        Path(f"__global/{env}.json"),
        Path(f"__global/{c}/{env}.json"),
        Path(f"__global/{c}/{s}/{env}.json"),
        Path(f"{d}/{env}.json"),
        Path(f"{d}/{c}/{env}.json"),
        Path(f"{d}/{c}/{s}/{env}.json"),
        Path(f"{d}/{c}/{s}/{cd}/{env}.json"),
    ]


def _mode_all_template_candidates(opts: InitOptions, mode: str) -> List[Path]:
    d = opts.domain
    c = opts.connector_type
    s = opts.system
    cd = opts.connector_dir
    return [
        Path(f"__global/modes/{mode}/all.json"),
        Path(f"__global/{c}/modes/{mode}/all.json"),
        Path(f"__global/{c}/{s}/modes/{mode}/all.json"),
        Path(f"{d}/modes/{mode}/all.json"),
        Path(f"{d}/{c}/modes/{mode}/all.json"),
        Path(f"{d}/{c}/{s}/modes/{mode}/all.json"),
        Path(f"{d}/{c}/{s}/{cd}/modes/{mode}/all.json"),
    ]


def _mode_env_template_candidates(opts: InitOptions, mode: str, env: str) -> List[Path]:
    d = opts.domain
    c = opts.connector_type
    s = opts.system
    cd = opts.connector_dir
    return [
        Path(f"__global/modes/{mode}/{env}.json"),
        Path(f"__global/{c}/modes/{mode}/{env}.json"),
        Path(f"__global/{c}/{s}/modes/{mode}/{env}.json"),
        Path(f"{d}/modes/{mode}/{env}.json"),
        Path(f"{d}/{c}/modes/{mode}/{env}.json"),
        Path(f"{d}/{c}/{s}/modes/{mode}/{env}.json"),
        Path(f"{d}/{c}/{s}/{cd}/modes/{mode}/{env}.json"),
    ]


def _type_all_template_candidates(opts: InitOptions, kind: str) -> List[Path]:
    d = opts.domain
    c = opts.connector_type
    s = opts.system
    cd = opts.connector_dir
    return [
        Path("__global/types/default/all.json"),
        Path(f"__global/types/{kind}/all.json"),
        Path(f"__global/{c}/types/default/all.json"),
        Path(f"__global/{c}/types/{kind}/all.json"),
        Path(f"__global/{c}/{s}/types/default/all.json"),
        Path(f"__global/{c}/{s}/types/{kind}/all.json"),
        Path(f"{d}/types/default/all.json"),
        Path(f"{d}/types/{kind}/all.json"),
        Path(f"{d}/{c}/types/default/all.json"),
        Path(f"{d}/{c}/types/{kind}/all.json"),
        Path(f"{d}/{c}/{s}/types/default/all.json"),
        Path(f"{d}/{c}/{s}/types/{kind}/all.json"),
        Path(f"{d}/{c}/{s}/{cd}/types/default/all.json"),
        Path(f"{d}/{c}/{s}/{cd}/types/{kind}/all.json"),
    ]


def _type_env_template_candidates(opts: InitOptions, kind: str, env: str) -> List[Path]:
    d = opts.domain
    c = opts.connector_type
    s = opts.system
    cd = opts.connector_dir
    return [
        Path(f"__global/types/default/{env}.json"),
        Path(f"__global/types/{kind}/{env}.json"),
        Path(f"__global/{c}/types/default/{env}.json"),
        Path(f"__global/{c}/types/{kind}/{env}.json"),
        Path(f"__global/{c}/{s}/types/default/{env}.json"),
        Path(f"__global/{c}/{s}/types/{kind}/{env}.json"),
        Path(f"{d}/types/default/{env}.json"),
        Path(f"{d}/types/{kind}/{env}.json"),
        Path(f"{d}/{c}/types/default/{env}.json"),
        Path(f"{d}/{c}/types/{kind}/{env}.json"),
        Path(f"{d}/{c}/{s}/types/default/{env}.json"),
        Path(f"{d}/{c}/{s}/types/{kind}/{env}.json"),
        Path(f"{d}/{c}/{s}/{cd}/types/default/{env}.json"),
        Path(f"{d}/{c}/{s}/{cd}/types/{kind}/{env}.json"),
    ]


def _apply_template_files(
    base: Dict[str, Any],
    layers: List[str],
    opts: InitOptions,
    candidates: Sequence[Path],
    *,
    log: logging.Logger,
) -> Dict[str, Any]:
    merged: Dict[str, Any] = base
    root = opts.templates_root

    for rel in candidates:
        p = (root / rel).resolve()
        if opts.fs.exists(p) and opts.fs.is_file(p):
            obj = _read_json_mapping(opts.fs, p, label=str(rel))
            merged = _deep_merge(merged, obj)
            layers.append(
                f"file:{rel} (vars={_count_leaf_keys(obj.get('vars') or {})}, config={_count_leaf_keys(obj.get('config') or {})})"
            )

    return merged


def _read_json_mapping(fs: FileSystem, path: Path, *, label: str) -> Dict[str, Any]:
    try:
        raw = fs.read_text(path)
        obj = json.loads(raw)
    except Exception as e:  # pragma: no cover
        raise ConfigError(f"Не удалось прочитать JSON шаблон {label}: {e}") from e
    if not isinstance(obj, dict):
        raise ConfigError(
            f"Шаблон {label} должен быть JSON object, а не {type(obj).__name__}"
        )
    return obj


# ---------------------------
# Overrides (env/CLI)
# ---------------------------


def _apply_overrides(
    base: Dict[str, Any],
    overrides: Sequence[InitTemplateOverride],
    *,
    target_relpath: str,
    allowed: Set[str],
    log: logging.Logger,
) -> Tuple[Dict[str, Any], List[str]]:
    merged = base
    applied: List[str] = []

    target_norm = str(target_relpath).replace("\\", "/")

    for ov in overrides:
        scope = (ov.scope or "").strip() or None
        if scope is not None:
            scope_norm = scope.replace("\\", "/")
            if not fnmatch.fnmatchcase(target_norm, scope_norm):
                continue

        if ov.kind == "json":
            patch = _filter_allowed(ov.payload, allowed)
            if patch:
                merged = _deep_merge(merged, patch)
                vars_n = _count_leaf_keys(patch.get("vars") or {})
                cfg_n = _count_leaf_keys(patch.get("config") or {})
                scope_s = f" scope={scope}" if scope is not None else ""
                applied.append(
                    f"{ov.label}{scope_s} ({ov.kind}, vars={vars_n}, config={cfg_n})"
                )
        elif ov.kind == "kv":
            patch = _kv_to_patch(merged, ov.payload, allowed=allowed)
            if patch:
                merged = _deep_merge(merged, patch)
                vars_n = _count_leaf_keys(patch.get("vars") or {})
                cfg_n = _count_leaf_keys(patch.get("config") or {})
                scope_s = f" scope={scope}" if scope is not None else ""
                applied.append(
                    f"{ov.label}{scope_s} ({ov.kind}, vars={vars_n}, config={cfg_n})"
                )
        else:  # pragma: no cover
            raise ConfigError(f"Неизвестный тип override: {ov.kind}")

    return merged, applied


def _filter_allowed(obj: Dict[str, Any], allowed: Set[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in ("vars", "config"):
        if k in obj and k in allowed:
            v = obj.get(k)
            if isinstance(v, dict):
                out[k] = v
    return out


def _kv_to_patch(
    current: Dict[str, Any], kv: Dict[str, Any], *, allowed: Set[str]
) -> Dict[str, Any]:
    vars_patch: Dict[str, Any] = {}
    cfg_patch: Dict[str, Any] = {}

    current_vars = current.get("vars") if isinstance(current.get("vars"), dict) else {}

    for k_raw, v in kv.items():
        k = str(k_raw).strip()
        if not k:
            continue

        if k.startswith("vars."):
            if "vars" not in allowed:
                continue
            path = [p for p in k[len("vars.") :].split(".") if p]
            _set_nested(vars_patch, path, v)
            continue

        if k.startswith("config."):
            if "config" not in allowed:
                continue
            cfg_key = k[len("config.") :].strip()
            if cfg_key:
                cfg_patch[cfg_key] = v
            continue

        # No explicit prefix: try vars-path first (only if vars exist + path exists in template)
        path = [p for p in k.split(".") if p]
        if "vars" in allowed and path and _path_exists(current_vars, path):
            _set_nested(vars_patch, path, v)
        elif "config" in allowed:
            # Kafka Connect config keys are flat strings (often with dots).
            cfg_patch[k] = v

    out: Dict[str, Any] = {}
    if vars_patch and "vars" in allowed:
        out["vars"] = vars_patch
    if cfg_patch and "config" in allowed:
        out["config"] = cfg_patch
    return out


def _path_exists(root: Any, path: Sequence[str]) -> bool:
    cur = root
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return False
        cur = cur[p]
    return True


def _set_nested(d: Dict[str, Any], path: Sequence[str], value: Any) -> None:
    cur = d
    for p in path[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    if path:
        cur[path[-1]] = value


# ---------------------------
# Utility
# ---------------------------


def _deep_merge(a: Any, b: Any) -> Any:
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            if k in out:
                out[k] = _deep_merge(out[k], v)
            else:
                out[k] = v
        return out
    return b


def _count_leaf_keys(obj: Any) -> int:
    if isinstance(obj, dict):
        total = 0
        for v in obj.values():
            total += _count_leaf_keys(v)
        return total
    return 1


__all__ = [
    "InitFileTemplateResult",
    "build_all_json",
    "build_env_json",
    "build_mode_all_json",
    "build_mode_env_json",
    "build_type_all_json",
    "build_type_env_json",
]
