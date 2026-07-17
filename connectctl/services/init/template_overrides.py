from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

from ...exceptions import ConfigError
from ...cli_helpers.patch_io_files import _read_text_file_or_dash
from ...cli_helpers.patch_io_json import _read_json_mapping_from_text
from ...cli_helpers.patch_io_kv import _parse_kv_pairs, _parse_kv_text

from .models import InitTemplateOverride


def _canonicalize_json_mapping(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Convert JSON mapping into a canonical overlay: {vars?, config?}.

    If JSON contains top-level keys `vars` and/or `config` — keep them.
    Otherwise treat the whole mapping as a `config` mapping (Kafka Connect keys).
    """
    if any(k in obj for k in ("vars", "config")):
        out: Dict[str, Any] = {}
        vars_obj = obj.get("vars")
        cfg_obj = obj.get("config")
        if isinstance(vars_obj, dict):
            out["vars"] = vars_obj
        if isinstance(cfg_obj, dict):
            out["config"] = cfg_obj
        # Ignore other keys on purpose: init-templates operate on vars/config only.
        return out
    return {"config": dict(obj)}


def _looks_like_scope(scope: str) -> bool:
    s = (scope or "").strip()
    if not s:
        return False
    # Typical scopes: all.json, prod.json, modes/init/*, types/events/*
    if s.startswith(("modes/", "types/")):
        return True
    if "/" in s:
        return True
    if any(ch in s for ch in "*?[]"):
        return True
    if s.endswith(".json"):
        return True
    return False


def _try_split_scoped_kv_arg(raw: str) -> tuple[str, str] | None:
    """Detect '<scope>:k=v[,k=v]' format for --tpl-set without breaking values like http://..."""
    s = (raw or "").strip()
    if not s:
        return None
    if ":" not in s or "=" not in s:
        return None
    colon_i = s.find(":")
    eq_i = s.find("=")
    # For scoped KV overrides, the scope delimiter ':' must appear before the first '='.
    # This avoids false positives for values like 'url=http://host:8083'.
    if 0 <= colon_i < eq_i:
        scope, payload = s.split(":", 1)
        scope = scope.strip()
        payload = payload.strip()
        if scope and payload:
            return scope, payload
    return None


def _try_split_scoped_json_inline(raw: str) -> tuple[str, str] | None:
    """Detect '<scope>:<json>' format for --tpl-json."""
    s = (raw or "").strip()
    if not s:
        return None
    # Unscoped JSON starts with '{' or '['.
    if s[:1] in "{[":
        return None
    if ":" not in s:
        return None
    scope, payload = s.split(":", 1)
    scope = scope.strip()
    payload2 = payload.lstrip()
    if scope and payload2[:1] in "{[":
        return scope, payload.strip()
    return None


def _try_split_scoped_file_arg(raw: str) -> tuple[str, str] | None:
    """Detect '<scope>:<path>' for --tpl-*-file without requiring a separate flag."""
    s = (raw or "").strip()
    if not s or ":" not in s:
        return None
    if s[:1] in "{[":
        return None
    scope, payload = s.split(":", 1)
    scope = scope.strip()
    payload = payload.strip()
    if not scope or not payload:
        return None
    # Heuristic: only treat as scoped when the left part looks like a scope.
    if _looks_like_scope(scope):
        return scope, payload
    # If the payload is '-' or an existing file, also accept (allows scopes without wildcards).
    if payload == "-" or os.path.exists(payload):
        return scope, payload
    return None


def collect_init_template_overrides(
    args: argparse.Namespace,
) -> List[InitTemplateOverride]:
    """Collect init-template overrides from env vars + CLI flags.

    Priority order (low -> high):
      1) env vars
      2) CLI flags (files -> inline -> stdin)

    Supported env vars:
      - BKKT_INIT_TPL       : JSON object or key=value pairs
      - BKKT_INIT_TPL_FILE  : path to file with JSON or key=value
      - BKKT_INIT_TPL_SCOPED      : JSON list/dict of scoped overrides
      - BKKT_INIT_TPL_SCOPED_FILE : path to file with scoped overrides JSON

    Supported CLI flags:
      - --tpl-json / --tpl-json-file
      - --tpl-set / --tpl-set-file
      - --tpl-stdin

    Scoped overrides (без отдельных флагов):
      - --tpl-json '<scope>:<json>'
      - --tpl-json-file '<scope>:<path>'
      - --tpl-set '<scope>:k=v[,k=v]'
      - --tpl-set-file '<scope>:<path>'

    Legacy scoped flags (поддерживаются, но не обязательны):
      - --tpl-json-scoped / --tpl-json-file-scoped
      - --tpl-set-scoped / --tpl-set-file-scoped
    """

    sources: List[InitTemplateOverride] = []

    # 1) env file
    env_file = (os.environ.get("BKKT_INIT_TPL_FILE") or "").strip()
    if env_file:
        txt = _read_text_file_or_dash(env_file)
        label = f"env:BKKT_INIT_TPL_FILE {env_file}"
        sources.extend(_parse_text_source(txt, label))

    # 2) env inline
    env_inline = (os.environ.get("BKKT_INIT_TPL") or "").strip()
    if env_inline:
        label = "env:BKKT_INIT_TPL"
        sources.extend(_parse_text_source(env_inline, label))

    # 2b) env scoped file
    env_scoped_file = (os.environ.get("BKKT_INIT_TPL_SCOPED_FILE") or "").strip()
    if env_scoped_file:
        txt = _read_text_file_or_dash(env_scoped_file)
        label = f"env:BKKT_INIT_TPL_SCOPED_FILE {env_scoped_file}"
        sources.extend(_parse_scoped_json_source(txt, label))

    # 2c) env scoped inline
    env_scoped_inline = (os.environ.get("BKKT_INIT_TPL_SCOPED") or "").strip()
    if env_scoped_inline:
        label = "env:BKKT_INIT_TPL_SCOPED"
        sources.extend(_parse_scoped_json_source(env_scoped_inline, label))

    # 3) CLI JSON files (также поддерживается scoped формат: <scope>:<path>)
    for jf in getattr(args, "tpl_json_file", None) or []:
        raw = str(jf)
        scoped = _try_split_scoped_file_arg(raw)
        if scoped:
            scope, path = scoped
            txt = _read_text_file_or_dash(path)
            obj = _read_json_mapping_from_text(
                txt, src_label=f"--tpl-json-file {scope}:{path}"
            )
            sources.append(
                InitTemplateOverride(
                    label=f"--tpl-json-file {scope}",
                    kind="json",
                    payload=_canonicalize_json_mapping(obj),
                    scope=scope,
                )
            )
            continue

        txt = _read_text_file_or_dash(raw)
        obj = _read_json_mapping_from_text(txt, src_label=f"--tpl-json-file {raw}")
        sources.append(
            InitTemplateOverride(
                label=f"--tpl-json-file {raw}",
                kind="json",
                payload=_canonicalize_json_mapping(obj),
            )
        )

    # 4) CLI JSON inline (также поддерживается scoped формат: <scope>:<json>)
    for js in getattr(args, "tpl_json", None) or []:
        raw = str(js)
        scoped = _try_split_scoped_json_inline(raw)
        if scoped:
            scope, json_text = scoped
            obj = _read_json_mapping_from_text(
                json_text, src_label=f"--tpl-json {scope}"
            )
            sources.append(
                InitTemplateOverride(
                    label=f"--tpl-json {scope}",
                    kind="json",
                    payload=_canonicalize_json_mapping(obj),
                    scope=scope,
                )
            )
            continue

        obj = _read_json_mapping_from_text(raw, src_label="--tpl-json")
        sources.append(
            InitTemplateOverride(
                label="--tpl-json", kind="json", payload=_canonicalize_json_mapping(obj)
            )
        )

    # 4b) CLI JSON scoped files: <scope>:<path>
    for raw in getattr(args, "tpl_json_file_scoped", None) or []:
        scope, path = _split_scope_arg(str(raw), label="--tpl-json-file-scoped")
        txt = _read_text_file_or_dash(path)
        obj = _read_json_mapping_from_text(
            txt, src_label=f"--tpl-json-file-scoped {scope}:{path}"
        )
        sources.append(
            InitTemplateOverride(
                label=f"--tpl-json-file-scoped {scope}",
                kind="json",
                payload=_canonicalize_json_mapping(obj),
                scope=scope,
            )
        )

    # 4c) CLI JSON scoped inline: <scope>:<json>
    for raw in getattr(args, "tpl_json_scoped", None) or []:
        scope, js = _split_scope_arg(str(raw), label="--tpl-json-scoped")
        obj = _read_json_mapping_from_text(
            str(js), src_label=f"--tpl-json-scoped {scope}"
        )
        sources.append(
            InitTemplateOverride(
                label=f"--tpl-json-scoped {scope}",
                kind="json",
                payload=_canonicalize_json_mapping(obj),
                scope=scope,
            )
        )

    # 5) CLI key=value files (также поддерживается scoped формат: <scope>:<path>)
    for sf in getattr(args, "tpl_set_file", None) or []:
        raw = str(sf)
        scoped = _try_split_scoped_file_arg(raw)
        if scoped:
            scope, path = scoped
            txt = _read_text_file_or_dash(path)
            kv = _parse_kv_text(txt)
            sources.append(
                InitTemplateOverride(
                    label=f"--tpl-set-file {scope}",
                    kind="kv",
                    payload=dict(kv),
                    scope=scope,
                )
            )
            continue

        txt = _read_text_file_or_dash(raw)
        kv = _parse_kv_text(txt)
        sources.append(
            InitTemplateOverride(
                label=f"--tpl-set-file {raw}", kind="kv", payload=dict(kv)
            )
        )

    # 6) CLI key=value inline (также поддерживается scoped формат: <scope>:k=v[,k=v])
    for s in getattr(args, "tpl_set", None) or []:
        raw = str(s)
        scoped = _try_split_scoped_kv_arg(raw)
        if scoped:
            scope, kv_text = scoped
            kv = _parse_kv_pairs(str(kv_text))
            sources.append(
                InitTemplateOverride(
                    label=f"--tpl-set {scope}",
                    kind="kv",
                    payload=dict(kv),
                    scope=scope,
                )
            )
            continue

        kv = _parse_kv_pairs(raw)
        sources.append(
            InitTemplateOverride(label="--tpl-set", kind="kv", payload=dict(kv))
        )

    # 6b) CLI key=value scoped files: <scope>:<path>
    for raw in getattr(args, "tpl_set_file_scoped", None) or []:
        scope, path = _split_scope_arg(str(raw), label="--tpl-set-file-scoped")
        txt = _read_text_file_or_dash(path)
        kv = _parse_kv_text(txt)
        sources.append(
            InitTemplateOverride(
                label=f"--tpl-set-file-scoped {scope}",
                kind="kv",
                payload=dict(kv),
                scope=scope,
            )
        )

    # 6c) CLI key=value scoped inline: <scope>:k=v[,k=v]
    for raw in getattr(args, "tpl_set_scoped", None) or []:
        scope, kv_text = _split_scope_arg(str(raw), label="--tpl-set-scoped")
        kv = _parse_kv_pairs(str(kv_text))
        sources.append(
            InitTemplateOverride(
                label=f"--tpl-set-scoped {scope}",
                kind="kv",
                payload=dict(kv),
                scope=scope,
            )
        )

    # 7) stdin (optional)
    if bool(getattr(args, "tpl_stdin", False)):
        if sys.stdin.isatty():
            raise ConfigError(
                "--tpl-stdin указан, но stdin пуст (TTY). Используйте pipe stdin."
            )
        raw = sys.stdin.read()
        if not (raw or "").strip():
            raise ConfigError("--tpl-stdin: stdin пуст")
        sources.extend(_parse_text_source(raw, "stdin"))

    return sources


def _parse_text_source(text: str, label: str) -> List[InitTemplateOverride]:
    raw = (text or "").strip()
    if not raw:
        return []
    if raw.startswith("{"):
        obj = _read_json_mapping_from_text(raw, src_label=label)
        return [
            InitTemplateOverride(
                label=label, kind="json", payload=_canonicalize_json_mapping(obj)
            )
        ]
    kv = _parse_kv_text(text)
    return [InitTemplateOverride(label=label, kind="kv", payload=dict(kv))]


def _split_scope_arg(raw: str, *, label: str) -> tuple[str, str]:
    """Разобрать CLI формат '<scope>:<payload>'."""

    s = (raw or "").strip()
    if ":" not in s:
        raise ConfigError(
            f"{label}: ожидается формат <scope>:<payload>. "
            f"Пример: 'modes/init/*:vars.x=1'. Получено: {raw!r}"
        )
    scope, payload = s.split(":", 1)
    scope = scope.strip()
    payload = payload.strip()
    if not scope:
        raise ConfigError(f"{label}: scope пуст")
    if not payload:
        raise ConfigError(f"{label}: payload пуст")
    return scope, payload


def _parse_scoped_json_source(text: str, label: str) -> List[InitTemplateOverride]:
    """Разобрать scoped overrides JSON.

    Формат:
      - JSON list: [{"scope": "types/events/*", "vars": {...}, "config": {...}}, ...]
      - JSON dict: {"scope": "modes/init/*", "vars": {...}}
    """

    raw = (text or "").strip()
    if not raw:
        return []

    try:
        obj = json.loads(raw)
    except Exception as e:
        raise ConfigError(f"{label}: не удалось распарсить JSON: {e}") from e

    items: List[Any]
    if isinstance(obj, list):
        items = obj
    elif isinstance(obj, dict):
        items = [obj]
    else:
        raise ConfigError(
            f"{label}: ожидается JSON list/dict, получено: {type(obj).__name__}"
        )

    out: List[InitTemplateOverride] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ConfigError(f"{label}: элемент #{i} должен быть object")
        scope = str(item.get("scope") or "").strip()
        if not scope:
            raise ConfigError(f"{label}: элемент #{i} не содержит scope")

        payload_obj: Dict[str, Any]
        payload_val = item.get("payload")
        if isinstance(payload_val, dict):
            payload_obj = dict(payload_val)
        else:
            payload_obj = {k: v for k, v in item.items() if k not in {"scope", "label"}}

        out.append(
            InitTemplateOverride(
                label=f"{label} scope={scope}",
                kind="json",
                payload=_canonicalize_json_mapping(payload_obj),
                scope=scope,
            )
        )

    return out


__all__ = ["collect_init_template_overrides"]
