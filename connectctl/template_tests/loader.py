from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml

from ..exceptions import ConnectCtlError
from .models import TemplateTestCase


class TemplateTestLoader:
    """Discovers golden render tests from `bkkt/templates/tests/**/*.yaml`."""

    DEFAULT_GLOB = "bkkt/templates/tests/**/*.yaml"

    def __init__(self, repo_root: Path, *, pattern: str | None = None) -> None:
        self.repo_root = repo_root.resolve()
        self.pattern = pattern or self.DEFAULT_GLOB

    def load(self) -> tuple[TemplateTestCase, ...]:
        return tuple(
            case for path in self._iter_files() for case in self._load_file(path)
        )

    def _iter_files(self) -> Iterable[Path]:
        yield from sorted(self.repo_root.glob(self.pattern))

    def _load_file(self, path: Path) -> list[TemplateTestCase]:
        try:
            path.resolve().relative_to(self.repo_root)
        except ValueError as e:
            raise ConnectCtlError(
                f"Template test file escapes repo root: {path}"
            ) from e
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ConnectCtlError(f"{path}: template test file must be a mapping")
        cases = raw.get("cases", []) or []
        if not isinstance(cases, list):
            raise ConnectCtlError(f"{path}: `cases` must be a list")
        return [
            _case_from_mapping(item, path=path, index=index)
            for index, item in enumerate(cases)
        ]


def _case_from_mapping(item: Any, *, path: Path, index: int) -> TemplateTestCase:
    if not isinstance(item, dict):
        raise ConnectCtlError(f"{path}: cases[{index}] must be a mapping")
    manifest = str(item.get("manifest", "")).strip()
    if not manifest:
        raise ConnectCtlError(f"{path}: cases[{index}].manifest is required")
    expect = item.get("expect", {}) or {}
    if not isinstance(expect, dict):
        raise ConnectCtlError(f"{path}: cases[{index}].expect must be a mapping")
    config = expect.get("config", {}) or {}
    if not isinstance(config, dict):
        raise ConnectCtlError(f"{path}: cases[{index}].expect.config must be a mapping")
    return TemplateTestCase(
        name=str(item.get("name") or f"template case {index + 1}"),
        manifest=manifest,
        expect_name=str(expect["name"]) if expect.get("name") is not None else None,
        expect_config=dict(config),
        expect_full_config=bool(expect.get("full_config", False)),
        source_path=path,
    )
