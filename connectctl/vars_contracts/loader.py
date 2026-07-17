from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..exceptions import ConnectCtlError
from .models import VarsSchema, VarsSchemaEntry


class VarsSchemaLoader:
    """Loads optional repo-local typed vars schema."""

    DEFAULT_PATH = Path("bkkt/vars.schema.yaml")

    def __init__(self, repo_root: Path, *, schema_path: str | None = None) -> None:
        self.repo_root = repo_root.resolve()
        self.schema_path = Path(schema_path) if schema_path else self.DEFAULT_PATH

    def load(self) -> VarsSchema:
        path = (self.repo_root / self.schema_path).resolve()
        try:
            path.relative_to(self.repo_root)
        except ValueError as e:
            raise ConnectCtlError("vars schema path must stay inside repo root") from e
        if not path.exists():
            return VarsSchema(path=None, entries=())

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ConnectCtlError(f"{path} must contain a YAML mapping")
        entries_raw = raw.get("vars", {}) or {}
        if not isinstance(entries_raw, dict):
            raise ConnectCtlError(f"{path}: `vars` must be a mapping")

        entries: list[VarsSchemaEntry] = []
        for key, item in entries_raw.items():
            if not isinstance(key, str) or not key.strip():
                raise ConnectCtlError(f"{path}: vars keys must be non-empty strings")
            if item is None:
                item = {}
            if not isinstance(item, dict):
                raise ConnectCtlError(f"{path}: vars.{key} must be a mapping")
            entries.append(_entry_from_mapping(key.strip(), item))
        return VarsSchema(path=path, entries=tuple(entries))


def _entry_from_mapping(key: str, item: dict[str, Any]) -> VarsSchemaEntry:
    raw_type = str(item.get("type", "any")).strip().lower()
    if raw_type == "integer":
        raw_type = "int"
    if raw_type not in {"string", "int", "float", "bool", "number", "any"}:
        raise ConnectCtlError(f"Unsupported vars schema type for {key!r}: {raw_type!r}")
    enum = item.get("enum", ()) or ()
    if enum and not isinstance(enum, list):
        raise ConnectCtlError(f"vars.{key}.enum must be a list")
    return VarsSchemaEntry(
        key=key,
        type=raw_type,  # type: ignore[arg-type]
        required=bool(item.get("required", False)),
        enum=tuple(enum),
        pattern=str(item["pattern"]) if item.get("pattern") is not None else None,
        deprecated=bool(item.get("deprecated", False)),
        deprecated_since=(
            str(item["deprecated_since"])
            if item.get("deprecated_since") is not None
            else None
        ),
        remove_after=(
            str(item["remove_after"]) if item.get("remove_after") is not None else None
        ),
        replacement=(
            str(item["replacement"]) if item.get("replacement") is not None else None
        ),
        sensitive=bool(item.get("sensitive", False)),
        description=str(item.get("description", "") or ""),
    )
