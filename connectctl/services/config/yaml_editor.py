from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ruamel.yaml import YAML

from ...exceptions import ConfigError
from ...ports.filesystem import FileSystem

YamlMutation = Callable[[Any], None]


class RoundTripYamlEditor:
    """Round-trip YAML editor that preserves comments, order and style."""

    def __init__(self, *, fs: FileSystem) -> None:
        self.fs = fs
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.default_flow_style = False

    def mutate(self, path: Path, mutation: YamlMutation) -> None:
        if not self.fs.exists(path):
            raise ConfigError(f"Config file not found: {path}")
        raw = self.fs.read_text(path, encoding="utf-8")
        data = self.yaml.load(raw)
        if data is None:
            raise ConfigError(f"Config file is empty: {path}")
        mutation(data)
        self.fs.write_text(path, self._dump(data), encoding="utf-8")

    def _dump(self, data: Any) -> str:
        import io

        stream = io.StringIO()
        self.yaml.dump(data, stream)
        return stream.getvalue()


__all__ = ["RoundTripYamlEditor", "YamlMutation"]
