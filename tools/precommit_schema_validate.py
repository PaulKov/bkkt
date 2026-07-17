#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, List

import yaml
from jsonschema import Draft7Validator

# NOTE: pre-commit runs local hooks via `python tools/<script>.py` without
# installing the project package. Make sure repo root is on sys.path so we can
# import `connectctl`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from connectctl.utils.env import expand_env_in_obj  # noqa: E402


ENV_FILE_RE = re.compile(r"^(dev|stage|prod)([._].+)?\.json$")


def _load_json(path: Path) -> Any:
    # Some generated/placeholder manifest fragments may be committed as empty
    # files (0 bytes). Treat them as an empty object so schema validation can
    # still run (and `pre-commit run -a` doesn't fail on JSON parsing).
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    return json.loads(raw)


def _load_yaml(path: Path) -> Any:
    raw = path.read_text(encoding="utf-8").strip()
    return yaml.safe_load(raw) or {}


def _validate(schema: dict, instance: Any, *, file: Path) -> List[str]:
    v = Draft7Validator(schema)
    errs = sorted(v.iter_errors(instance), key=lambda e: list(e.path))
    out: List[str] = []
    for e in errs:
        loc = ".".join(str(p) for p in e.path) if e.path else "(root)"
        out.append(f"{file}:{loc}: {e.message}")
    return out


def main(argv: List[str]) -> int:
    schemas_dir = REPO_ROOT / "schemas"
    connectctl_schema = _load_json(schemas_dir / "connectctl.schema.json")
    manifest_schema = _load_json(schemas_dir / "manifest.schema.json")

    files = [Path(a) for a in argv[1:]]
    issues: List[str] = []

    for p in files:
        if not p.exists():
            continue

        name = p.name
        suf = p.suffix.lower()

        # connectctl.yaml / json
        if name in {"connectctl.yaml", "connectctl.yml"} and suf in {".yaml", ".yml"}:
            try:
                data = expand_env_in_obj(_load_yaml(p))
            except Exception as e:
                issues.append(f"{p}: invalid YAML: {e}")
                continue
            issues.extend(_validate(connectctl_schema, data, file=p))
            continue

        if name == "connectctl.json" and suf == ".json":
            try:
                data = _load_json(p)
            except Exception as e:
                issues.append(f"{p}: invalid JSON: {e}")
                continue
            issues.extend(_validate(connectctl_schema, data, file=p))
            continue

        # manifest fragments (best-effort heuristics)
        if suf == ".json" and (name == "all.json" or ENV_FILE_RE.match(name)):
            try:
                data = _load_json(p)
            except Exception as e:
                issues.append(f"{p}: invalid JSON: {e}")
                continue
            issues.extend(_validate(manifest_schema, data, file=p))

    if issues:
        sys.stderr.write("BKKT pre-commit: schema validation failed\n")
        for it in issues[:50]:
            sys.stderr.write(f"  - {it}\n")
        if len(issues) > 50:
            sys.stderr.write(f"  - … и ещё {len(issues) - 50}…\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
