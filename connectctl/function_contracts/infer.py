from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..exceptions import ConnectCtlError


@dataclass(frozen=True)
class InferredFunctionContract:
    """One generated contract-test case for a repo-local render function."""

    function: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] | None = None
    expect: Any = None
    manifest: str | None = None
    name: str | None = None

    def to_case_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name or f"{self.function} inferred case",
            "function": self.function,
            "args": list(self.args),
        }
        if self.kwargs:
            payload["kwargs"] = dict(self.kwargs)
        if self.manifest:
            payload["manifest"] = self.manifest
        payload["expect"] = self.expect
        return payload

    def to_file_payload(self) -> dict[str, Any]:
        return {"cases": [self.to_case_payload()]}

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.to_file_payload(),
            sort_keys=False,
            allow_unicode=True,
        )

    def write(self, *, repo_root: Path, path: Path, overwrite: bool = False) -> Path:
        target = _safe_repo_path(repo_root, path)
        if target.exists() and not overwrite:
            raise ConnectCtlError(
                f"Function contract target already exists: {target}. "
                "Use --overwrite explicitly."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_yaml(), encoding="utf-8")
        return target


def default_contract_path(function: str) -> Path:
    return Path("bkkt/functions/tests") / f"{_file_stem(function)}.yaml"


def _safe_repo_path(repo_root: Path, raw_path: Path) -> Path:
    target = raw_path if raw_path.is_absolute() else repo_root / raw_path
    target = target.resolve()
    try:
        target.relative_to(repo_root.resolve())
    except ValueError as e:
        raise ConnectCtlError("--output-file must stay inside repo root") from e
    return target


def _file_stem(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name) or "fn"
