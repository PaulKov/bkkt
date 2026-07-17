from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..repo import ConnectorRepo
from ..rendering.factory import build_renderer
from ..settings_models import Settings


@dataclass(frozen=True)
class InferredVar:
    key: str
    type: str
    sources: tuple[str, ...]
    manifests: tuple[str, ...]

    def to_schema_entry(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "required": False,
            "description": (
                "Inferred by `bkkt vars schema infer --from-repo`; "
                f"seen in {len(self.manifests)} manifest(s)."
            ),
        }

    def to_payload(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "type": self.type,
            "sources": list(self.sources),
            "manifests": list(self.manifests),
        }


@dataclass(frozen=True)
class InferredVarsSchema:
    vars: tuple[InferredVar, ...]

    def to_schema_payload(self) -> dict[str, Any]:
        return {
            "version": 1,
            "vars": {
                item.key: item.to_schema_entry()
                for item in sorted(self.vars, key=lambda var: var.key)
            },
        }

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema": self.to_schema_payload(),
            "inferred": [item.to_payload() for item in self.vars],
            "summary": {"vars": len(self.vars)},
        }

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.to_schema_payload(),
            sort_keys=False,
            allow_unicode=True,
        )


class VarsSchemaInferer:
    """Infers a starter typed vars schema from rendered deployable manifests."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repo = ConnectorRepo(settings.repo)

    def infer(self) -> InferredVarsSchema:
        values_by_key: dict[str, list[Any]] = defaultdict(list)
        sources_by_key: dict[str, set[str]] = defaultdict(set)
        manifests_by_key: dict[str, set[str]] = defaultdict(set)
        renderer = build_renderer(self.settings)

        for manifest_path in sorted(self.repo.iter_deployable_connector_files()):
            rendered = renderer.render(manifest_path)
            rel_manifest = self._relative(manifest_path)
            for usage in rendered.vars_used:
                if usage.key not in rendered.placeholder_context:
                    continue
                values_by_key[usage.key].append(rendered.placeholder_context[usage.key])
                sources_by_key[usage.key].add(usage.source)
                manifests_by_key[usage.key].add(rel_manifest)

        return InferredVarsSchema(
            vars=tuple(
                InferredVar(
                    key=key,
                    type=_infer_type(values_by_key[key]),
                    sources=tuple(sorted(sources_by_key[key])),
                    manifests=tuple(sorted(manifests_by_key[key])),
                )
                for key in sorted(values_by_key)
            )
        )

    def _relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.settings.repo.root).as_posix()
        except ValueError:
            return str(path)


def write_schema_file(
    schema: InferredVarsSchema,
    *,
    path: Path,
    overwrite: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        from ..exceptions import ConnectCtlError

        raise ConnectCtlError(
            f"Vars schema target already exists: {path}. Use --overwrite explicitly."
        )
    path.write_text(schema.to_yaml(), encoding="utf-8")


def _infer_type(values: list[Any]) -> str:
    observed = {_type_name(value) for value in values}
    if not observed:
        return "any"
    if observed == {"int"}:
        return "int"
    if observed <= {"int", "float"}:
        return "number"
    if observed == {"bool"}:
        return "bool"
    if observed == {"string"}:
        return "string"
    return "any"


def _type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    return "any"
