from __future__ import annotations

from pathlib import Path
from typing import Any

from ..rendering.factory import build_renderer
from ..settings_models import Settings
from ..template_inventory import TemplateInventoryScanner, TemplateUsage
from .models import RenderDiff, TemplateImpactReport


class TemplateImpactService:
    """Repo-wide impact analysis for variables and functions."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repo_root = settings.repo.root.resolve()
        self.inventory = TemplateInventoryScanner(settings).scan()

    def variable_impact(
        self,
        name: str,
        *,
        override_value: Any | None = None,
        with_render_diff: bool = False,
    ) -> TemplateImpactReport:
        matches = self.inventory.used_by_variable(name)
        diffs: tuple[RenderDiff, ...] = ()
        if with_render_diff and override_value is not None:
            diffs = self._render_diffs(
                matches,
                runtime_vars=_dotted_to_nested(name, override_value),
                runtime_var_sources={name: "impact:set"},
            )
        return TemplateImpactReport(
            kind="variable",
            name=name,
            matches=matches,
            render_diffs=diffs,
        )

    def function_impact(
        self,
        name: str,
        *,
        with_render_diff: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> TemplateImpactReport:
        matches = self.inventory.used_by_function(name)
        diffs = self._render_diffs(matches) if with_render_diff else ()
        return TemplateImpactReport(
            kind="function",
            name=name,
            matches=matches,
            render_diffs=diffs,
            metadata=metadata,
        )

    def _render_diffs(
        self,
        matches: tuple[TemplateUsage, ...],
        *,
        runtime_vars: dict[str, Any] | None = None,
        runtime_var_sources: dict[str, str] | None = None,
    ) -> tuple[RenderDiff, ...]:
        renderer = build_renderer(self.settings)
        diffs: set[RenderDiff] = set()
        for manifest in sorted({item.manifest for item in matches}):
            path = self.repo_root / manifest
            before = renderer.render(path).manifest.config
            after = renderer.render(
                path,
                runtime_vars=runtime_vars,
                runtime_var_sources=runtime_var_sources,
            ).manifest.config
            for key in sorted(set(before) | set(after)):
                before_value = before.get(key)
                after_value = after.get(key)
                if before_value != after_value:
                    diffs.add(
                        RenderDiff(
                            manifest=_relative(self.repo_root, path),
                            config_key=key,
                            before=before_value,
                            after=after_value,
                        )
                    )
        return tuple(sorted(diffs))


def _dotted_to_nested(name: str, value: Any) -> dict[str, Any]:
    parts = [part for part in name.split(".") if part]
    if not parts:
        return {}
    root: dict[str, Any] = {}
    cursor = root
    for part in parts[:-1]:
        nested: dict[str, Any] = {}
        cursor[part] = nested
        cursor = nested
    cursor[parts[-1]] = value
    return root


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)
