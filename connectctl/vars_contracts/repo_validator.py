from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..repo import ConnectorRepo
from ..rendering.factory import build_renderer
from ..settings_models import Settings
from .models import VarsDoctorResult, VarsSchema
from .validator import VarsSchemaValidator


@dataclass(frozen=True)
class RepoVarsValidationItem:
    manifest: str
    result: VarsDoctorResult

    @property
    def failed(self) -> bool:
        return self.result.status == "failed"

    def to_payload(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest,
            "status": self.result.status,
            "issues": [issue.to_payload() for issue in self.result.issues],
        }


@dataclass(frozen=True)
class RepoVarsValidationResult:
    items: tuple[RepoVarsValidationItem, ...]

    @property
    def status(self) -> str:
        return "failed" if any(item.failed for item in self.items) else "ok"

    @property
    def exit_code(self) -> int:
        return 1 if self.status == "failed" else 0

    def to_payload(self) -> dict[str, Any]:
        ordered = sorted(self.items, key=lambda item: (not item.failed, item.manifest))
        return {
            "status": self.status,
            "summary": {
                "manifests": len(self.items),
                "failed": sum(1 for item in self.items if item.failed),
            },
            "results": [item.to_payload() for item in ordered],
        }


class RepoVarsValidator:
    """Validates every deployable manifest against a typed vars schema."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repo = ConnectorRepo(settings.repo)

    def validate(self, schema: VarsSchema) -> RepoVarsValidationResult:
        renderer = build_renderer(self.settings)
        validator = VarsSchemaValidator()
        items: list[RepoVarsValidationItem] = []
        for manifest_path in sorted(self.repo.iter_deployable_connector_files()):
            rendered = renderer.render(manifest_path)
            result = validator.validate(
                schema,
                rendered.placeholder_context,
                sources=rendered.placeholder_sources,
            )
            items.append(
                RepoVarsValidationItem(
                    manifest=_relative(manifest_path, self.settings.repo.root),
                    result=result,
                )
            )
        return RepoVarsValidationResult(items=tuple(items))


def _relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)
