from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Sequence

import yaml
from jsonschema import Draft7Validator

from ..exceptions import ValidationError
from ..ports import FileSystem
from ..utils import expand_env_in_obj


@dataclass(frozen=True)
class SchemaIssue:
    """One JSON Schema validation issue."""

    file: Path
    message: str
    instance_path: str = ""
    schema_path: str = ""

    def short(self) -> str:
        loc = self.instance_path or "(root)"
        return f"{self.file.as_posix()}: {loc}: {self.message}"


def _load_yaml_or_json(path: Path, *, fs: FileSystem) -> Any:
    raw = fs.read_text(path).strip()
    if not raw:
        return {}
    suf = path.suffix.lower()
    if suf in {".yaml", ".yml"}:
        data = yaml.safe_load(raw) or {}
        return expand_env_in_obj(data)
    if suf == ".json":
        return json.loads(raw)
    raise ValidationError(
        f"Unsupported format for schema validation: {path.suffix} ({path})"
    )


def load_schema(schema_path: Path, *, fs: FileSystem) -> dict:
    if not fs.exists(schema_path):
        raise ValidationError(f"Schema file not found: {schema_path}")
    raw = fs.read_text(schema_path)
    return json.loads(raw)


def validate_instance(
    instance: Any,
    *,
    schema: dict,
    file: Path,
) -> List[SchemaIssue]:
    v = Draft7Validator(schema)
    issues: List[SchemaIssue] = []
    for e in sorted(v.iter_errors(instance), key=lambda x: list(x.path)):
        inst_path = ".".join(str(p) for p in e.path) if e.path else ""
        sch_path = ".".join(str(p) for p in e.schema_path) if e.schema_path else ""
        issues.append(
            SchemaIssue(
                file=file,
                message=str(e.message),
                instance_path=inst_path,
                schema_path=sch_path,
            )
        )
    return issues


def validate_file(
    file: Path,
    *,
    schema: dict,
    fs: FileSystem,
) -> List[SchemaIssue]:
    try:
        data = _load_yaml_or_json(file, fs=fs)
    except json.JSONDecodeError as e:
        return [SchemaIssue(file=file, message=f"Invalid JSON: {e}")]
    except Exception as e:
        return [SchemaIssue(file=file, message=str(e))]

    return validate_instance(data, schema=schema, file=file)


def format_schema_issues(issues: Sequence[SchemaIssue], *, max_items: int = 20) -> str:
    total = len(issues)
    shown = list(issues[: max_items if max_items > 0 else total])
    lines = ["Schema validation issues:"]
    for it in shown:
        lines.append(f"- {it.short()}")
    if max_items > 0 and total > max_items:
        lines.append(f"- … и ещё {total - max_items}…")
    return "\n".join(lines)
