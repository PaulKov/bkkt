from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from ..exceptions import ConnectCtlError
from ..repo import ConnectorRepo
from ..settings_models import Settings
from ..template_graph import TemplateGraphExtractor
from .models import TemplateInventory, TemplateUsage


class TemplateInventoryScanner:
    """Scans manifests for repo-wide `${...}` and `${fn:...}` usage."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repo = ConnectorRepo(settings.repo)
        self.extractor = TemplateGraphExtractor()

    def scan(self) -> TemplateInventory:
        variables: dict[str, set[TemplateUsage]] = defaultdict(set)
        functions: dict[str, set[TemplateUsage]] = defaultdict(set)

        for path in self.repo.iter_json_files():
            rel_path = self._relative(path)
            config = self._load_config(path)
            graph = self.extractor.extract_from_config(config)
            fn_to_config = self._function_config_targets(graph.edges)

            for edge in graph.edges:
                if edge.from_id.startswith("var:") and edge.to_id.startswith("config:"):
                    variables[edge.from_id.removeprefix("var:")].add(
                        TemplateUsage(
                            manifest=rel_path,
                            config_key=edge.to_id.removeprefix("config:"),
                            kind=edge.kind,
                        )
                    )
                elif edge.from_id.startswith("fn:") and edge.to_id.startswith(
                    "config:"
                ):
                    functions[edge.from_id.removeprefix("fn:")].add(
                        TemplateUsage(
                            manifest=rel_path,
                            config_key=edge.to_id.removeprefix("config:"),
                            kind=edge.kind,
                        )
                    )
                elif edge.from_id.startswith("var:") and edge.to_id.startswith("fn:"):
                    var_name = edge.from_id.removeprefix("var:")
                    fn_name = edge.to_id.removeprefix("fn:")
                    for config_key in fn_to_config.get(fn_name, ()):
                        variables[var_name].add(
                            TemplateUsage(
                                manifest=rel_path,
                                config_key=config_key,
                                kind=edge.kind,
                                via_function=fn_name,
                            )
                        )

        return TemplateInventory(
            variable_usages={
                key: tuple(sorted(value)) for key, value in sorted(variables.items())
            },
            function_usages={
                key: tuple(sorted(value)) for key, value in sorted(functions.items())
            },
        )

    def _load_config(self, path: Path) -> dict[str, Any]:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except OSError as e:
            raise ConnectCtlError(f"Failed to read manifest: {path}") from e
        if not isinstance(raw, dict):
            raise ConnectCtlError(f"{path}: manifest must be a mapping")
        config = raw.get("config", {}) or {}
        if not isinstance(config, dict):
            raise ConnectCtlError(f"{path}: `config` must be a mapping")
        return config

    def _relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.settings.repo.root).as_posix()
        except ValueError:
            return str(path)

    @staticmethod
    def _function_config_targets(edges) -> dict[str, tuple[str, ...]]:
        targets: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            if edge.from_id.startswith("fn:") and edge.to_id.startswith("config:"):
                targets[edge.from_id.removeprefix("fn:")].add(
                    edge.to_id.removeprefix("config:")
                )
        return {key: tuple(sorted(value)) for key, value in targets.items()}
