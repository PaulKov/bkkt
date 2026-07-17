from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

from .models import LockedFunction


class FunctionFingerprinter:
    """Build deterministic fingerprints for function lockfiles."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()

    def lock_function(self, item: Any) -> LockedFunction:
        source_path = self._relative_path(item.source_path)
        payload = {
            "name": item.name,
            "source": item.source,
            "source_path": source_path,
            "source_text": self._source_text(item),
            "description": item.description.strip(),
            "lifecycle": item.lifecycle_payload(),
            "capabilities": list(item.capabilities),
        }
        fingerprint = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
        )
        return LockedFunction(
            name=item.name,
            package=item.package,
            source=item.source,
            source_path=source_path,
            fingerprint=fingerprint,
            description=item.description.strip(),
            capabilities=tuple(item.capabilities),
            lifecycle=item.lifecycle_payload(),
        )

    def _source_text(self, item: Any) -> str:
        try:
            return inspect.getsource(item.fn).strip()
        except (OSError, TypeError):
            return repr(item.fn)

    def _relative_path(self, path: Path | None) -> str | None:
        if path is None:
            return None
        try:
            return path.resolve().relative_to(self.repo_root).as_posix()
        except ValueError:
            return str(path)
