from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional

import yaml

from ..exceptions import ConfigError
from ..utils import deep_merge


def _parse_vars_file_args(vars_files: Optional[List[str]], repo_root: Path) -> dict:
    """Parse --vars-file JSON/YAML files into a single dict.

    Multiple --vars-file are merged (later wins for scalar keys; dicts deep-merged).
    Files must contain a mapping/object at the root.
    Relative paths are resolved from CWD first, then repo root.
    """

    merged: dict = {}
    if not vars_files:
        return merged

    stdin_used = False

    for raw in vars_files:
        raw = (raw or "").strip()
        if not raw:
            continue

        if raw == "-":
            if stdin_used:
                raise ConfigError("--vars-file - can only be used once")
            stdin_used = True
            stdin = sys.stdin
            isatty = getattr(stdin, "isatty", lambda: False)()
            if isatty:
                raise ConfigError(
                    "--vars-file - expects JSON/YAML via stdin; use a pipe or heredoc (e.g. --vars-file - <<'EOF' ... EOF)"
                )
            try:
                content = stdin.read()
            except Exception as e:
                raise ConfigError("Failed to read --vars-file from stdin") from e
            if not (content or "").strip():
                raise ConfigError("--vars-file - got empty stdin")

            try:
                # attempt JSON first, then YAML
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
                    f"--vars-file - must contain a JSON/YAML object (mapping) at root, got {type(obj).__name__}"
                )
            merged = deep_merge(merged, obj)
            continue

        p = Path(raw).expanduser()
        if not p.is_absolute():
            cwd_p = Path.cwd() / p
            repo_p = repo_root / p
            if cwd_p.exists():
                p = cwd_p.resolve()
            elif repo_p.exists():
                p = repo_p.resolve()
            else:
                # fall back to CWD for clearer error messages
                p = cwd_p.resolve()

        if not p.exists():
            raise ConfigError(f"--vars-file not found: {str(p)}")

        try:
            content = p.read_text(encoding="utf-8")
        except OSError as e:
            raise ConfigError(f"Failed to read --vars-file: {str(p)}") from e

        suffix = p.suffix.lower()
        try:
            if suffix == ".json":
                obj = json.loads(content)
            elif suffix in (".yaml", ".yml"):
                obj = yaml.safe_load(content)
            else:
                # attempt JSON first, then YAML
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
                f"--vars-file must contain a JSON/YAML object (mapping) at root, got {type(obj).__name__} in {str(p)}"
            )

        merged = deep_merge(merged, obj)

    return merged
