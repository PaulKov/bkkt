from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

from ..exceptions import ConfigError
from ..utils import deep_merge, flatten_dict
from ..vars_profiles import VarsProfileLoader
from .runtime_vars_files import _parse_vars_file_args
from .runtime_vars_parse import _parse_vars_arg


def _load_runtime_vars(args: argparse.Namespace, repo_root: Path) -> dict:
    """Load runtime vars from --vars-file and --vars, with --vars overriding files."""

    profile_vars = _load_profile_vars(args, repo_root)
    file_vars = _parse_vars_file_args(
        getattr(args, "vars_file", None), repo_root=repo_root
    )
    cli_vars = _parse_vars_arg(getattr(args, "vars", None))
    return deep_merge(deep_merge(profile_vars, file_vars), cli_vars)


def _load_runtime_vars_with_sources(
    args: argparse.Namespace, repo_root: Path
) -> Tuple[dict, Dict[str, str]]:
    """Like _load_runtime_vars, but also returns provenance for flattened keys.

    Source labels:
    - vars_file:<relpath|stdin>
    - cli
    """

    merged: dict = {}
    sources: Dict[str, str] = {}

    for profile_name in _profile_names(args):
        profile = VarsProfileLoader(repo_root).get(profile_name)
        for key in flatten_dict(profile.values).keys():
            sources[key] = f"vars_profile:{profile.name}"
        merged = deep_merge(merged, profile.values)

    vars_files = getattr(args, "vars_file", None) or []
    stdin_used = False
    for raw in vars_files:
        raw = (raw or "").strip()
        if not raw:
            continue
        label: str
        if raw == "-":
            if stdin_used:
                raise ConfigError("--vars-file - can only be used once")
            stdin_used = True
            stdin = sys.stdin
            isatty = getattr(stdin, "isatty", lambda: False)()
            if isatty:
                raise ConfigError("--vars-file - expects JSON/YAML via stdin")
            content = stdin.read()
            if not (content or "").strip():
                raise ConfigError("--vars-file - got empty stdin")
            try:
                try:
                    obj = json.loads(content)
                except Exception:
                    obj = yaml.safe_load(content)
            except Exception as e:
                raise ConfigError(
                    "--vars-file - must be valid JSON/YAML mapping from stdin"
                ) from e
            if obj is None:
                obj = {}
            if not isinstance(obj, dict):
                raise ConfigError(
                    f"--vars-file - must contain a mapping, got {type(obj).__name__}"
                )
            label = "vars_file:stdin"
        else:
            p = Path(raw).expanduser()
            if not p.is_absolute():
                cwd_p = Path.cwd() / p
                repo_p = repo_root / p
                if cwd_p.exists():
                    p = cwd_p.resolve()
                elif repo_p.exists():
                    p = repo_p.resolve()
                else:
                    p = cwd_p.resolve()
            if not p.exists():
                raise ConfigError(f"--vars-file not found: {str(p)}")
            content = p.read_text(encoding="utf-8")
            suffix = p.suffix.lower()
            try:
                if suffix == ".json":
                    obj = json.loads(content)
                elif suffix in (".yaml", ".yml"):
                    obj = yaml.safe_load(content)
                else:
                    try:
                        obj = json.loads(content)
                    except Exception:
                        obj = yaml.safe_load(content)
            except Exception as e:
                raise ConfigError(
                    f"--vars-file must be valid JSON/YAML mapping, got parse error in {str(p)}"
                ) from e
            if obj is None:
                obj = {}
            if not isinstance(obj, dict):
                raise ConfigError(
                    f"--vars-file must contain a mapping, got {type(obj).__name__} in {str(p)}"
                )
            try:
                rel = p.relative_to(repo_root)
                label = f"vars_file:{rel.as_posix()}"
            except Exception:
                label = f"vars_file:{p}"

        for k in flatten_dict(obj).keys():
            sources[k] = label
        merged = deep_merge(merged, obj)

    cli_vars_list = getattr(args, "vars", None) or []
    for raw in cli_vars_list:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ConfigError(
                f"--vars must be a JSON object (mapping), got {type(obj).__name__}"
            )
        for k in flatten_dict(obj).keys():
            sources[k] = "cli"
        merged = deep_merge(merged, obj)

    return merged, sources


def _load_profile_vars(args: argparse.Namespace, repo_root: Path) -> dict:
    merged: dict = {}
    loader = VarsProfileLoader(repo_root)
    for profile_name in _profile_names(args):
        merged = deep_merge(merged, loader.get(profile_name).values)
    return merged


def _profile_names(args: argparse.Namespace) -> list[str]:
    raw = getattr(args, "vars_profile", None) or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(item).strip() for item in raw if str(item).strip()]


def _print_vars_used(rr: Any, repo_root: Path, *, logger=None) -> None:
    """Log vars provenance per connector (best-effort)."""

    # Imported lazily to keep this module dependency-light.
    from ..logging_utils import get_logger
    from ..vars_contracts import VarsRedactor, VarsSchemaLoader

    log = get_logger(logger)
    redactor = VarsRedactor(VarsSchemaLoader(repo_root).load())
    vars_used = getattr(rr, "vars_used", None) or ()
    if not vars_used:
        return
    manifest = rr.manifest
    try:
        rel = manifest.source_path.resolve().relative_to(repo_root).as_posix()
    except Exception:
        rel = str(manifest.source_path)

    log.info("[vars] %s  (%s)", manifest.name, rel)
    for v in vars_used:
        log.info(
            "  - %s = %s  (from %s)",
            v.key,
            redactor.redact_value(v.key, v.value),
            v.source,
        )
