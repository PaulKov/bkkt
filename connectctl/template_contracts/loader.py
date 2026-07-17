from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml

from ..exceptions import ConnectCtlError
from .models import TemplateContract, TemplateContractInput


class TemplateContractLoader:
    """Loads repo-local template contracts from YAML files."""

    DEFAULT_GLOB = "bkkt/templates/contracts/**/*.yaml"

    def __init__(self, repo_root: Path, *, contract_path: str | None = None) -> None:
        self.repo_root = repo_root.resolve()
        self.contract_path = contract_path

    def load(self) -> tuple[TemplateContract, ...]:
        return tuple(
            contract
            for path in self._iter_files()
            for contract in self._load_file(path)
        )

    def _iter_files(self) -> Iterable[Path]:
        if self.contract_path:
            path = (self.repo_root / self.contract_path).resolve()
            self._assert_inside_repo(path)
            if not path.exists():
                raise ConnectCtlError(f"Template contract file does not exist: {path}")
            yield path
            return
        yield from sorted(self.repo_root.glob(self.DEFAULT_GLOB))

    def _load_file(self, path: Path) -> list[TemplateContract]:
        self._assert_inside_repo(path.resolve())
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ConnectCtlError(f"{path}: template contract file must be a mapping")
        contracts = raw.get("contracts", []) or []
        if not isinstance(contracts, list):
            raise ConnectCtlError(f"{path}: `contracts` must be a list")
        return [
            _contract_from_mapping(item, path=path, index=index)
            for index, item in enumerate(contracts)
        ]

    def _assert_inside_repo(self, path: Path) -> None:
        try:
            path.relative_to(self.repo_root)
        except ValueError as e:
            raise ConnectCtlError(
                f"Template contract path escapes repo root: {path}"
            ) from e


def _contract_from_mapping(item: Any, *, path: Path, index: int) -> TemplateContract:
    if not isinstance(item, dict):
        raise ConnectCtlError(f"{path}: contracts[{index}] must be a mapping")
    name = str(item.get("name") or f"template contract {index + 1}")
    manifests_raw = item.get("manifests", ()) or ()
    if isinstance(manifests_raw, str):
        manifests_raw = [manifests_raw]
    if not isinstance(manifests_raw, list) or not all(
        isinstance(value, str) and value.strip() for value in manifests_raw
    ):
        raise ConnectCtlError(f"{path}: contracts[{index}].manifests must be strings")
    inputs_raw = item.get("inputs", {}) or {}
    if not isinstance(inputs_raw, dict):
        raise ConnectCtlError(f"{path}: contracts[{index}].inputs must be a mapping")
    inputs = tuple(
        _input_from_mapping(str(key), value, path=path)
        for key, value in inputs_raw.items()
    )
    return TemplateContract(
        name=name,
        manifests=tuple(value.strip() for value in manifests_raw),
        inputs=inputs,
        source_path=path,
    )


def _input_from_mapping(key: str, item: Any, *, path: Path) -> TemplateContractInput:
    if item is None:
        item = {}
    if not isinstance(item, dict):
        raise ConnectCtlError(f"{path}: inputs.{key} must be a mapping")
    raw_type = str(item.get("type", "any")).strip().lower()
    if raw_type == "integer":
        raw_type = "int"
    if raw_type not in {"string", "int", "float", "bool", "number", "any"}:
        raise ConnectCtlError(f"{path}: unsupported input type for {key!r}: {raw_type}")
    enum = item.get("enum", ()) or ()
    if enum and not isinstance(enum, list):
        raise ConnectCtlError(f"{path}: inputs.{key}.enum must be a list")
    return TemplateContractInput(
        key=key,
        type=raw_type,  # type: ignore[arg-type]
        required=bool(item.get("required", False)),
        enum=tuple(enum),
        pattern=str(item["pattern"]) if item.get("pattern") is not None else None,
        default=item.get("default"),
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
        description=str(item.get("description", "") or ""),
    )
