from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RepoLayoutIssue:
    """Repo-wide lint finding (not tied to a single manifest file)."""

    severity: str  # "warn" | "error"
    policy: str
    domain: str
    connector_type: str
    system: str
    connector_dir: str
    path: str
    message: str
    hint: Optional[str] = None


# connector_<domain>__<dataset>{__<optional_suffix>}
CONNECTOR_DIR_DATASET_RE = re.compile(r"^[a-zA-Z0-9_]+$")
