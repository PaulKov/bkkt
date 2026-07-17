from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


ScaffoldStatus = Literal["planned", "created"]
ChecklistStatus = Literal["ok", "warning", "failed"]


@dataclass(frozen=True)
class ScaffoldFile:
    kind: str
    path: Path
    content: str

    def to_payload(self, *, repo_root: Path) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": _relative(repo_root, self.path),
            "content": self.content,
        }


@dataclass(frozen=True)
class FunctionScaffoldPlan:
    status: ScaffoldStatus
    files: tuple[ScaffoldFile, ...]

    def to_payload(self, *, repo_root: Path) -> dict[str, Any]:
        return {
            "kind": "function_scaffold",
            "status": self.status,
            "summary": {"files": len(self.files)},
            "files": [item.to_payload(repo_root=repo_root) for item in self.files],
        }


@dataclass(frozen=True)
class ReviewChecklistItem:
    code: str
    status: ChecklistStatus
    message: str

    def to_payload(self) -> dict[str, str]:
        return {
            "code": self.code,
            "status": self.status,
            "message": self.message,
        }


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)
