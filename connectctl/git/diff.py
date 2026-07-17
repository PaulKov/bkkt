from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from ..exceptions import GitError


@dataclass(frozen=True)
class ChangedPath:
    status: str  # M/A/D/R...
    path: Path
    old_path: Optional[Path] = None  # for renames


def _run_git(args: Sequence[str], cwd: Optional[Path] = None) -> str:
    try:
        out = subprocess.check_output(
            ["git", *args], cwd=str(cwd) if cwd else None, stderr=subprocess.STDOUT
        )
        return out.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError as e:
        raise GitError(
            f"Git command failed: git {' '.join(args)}\n{e.output.decode('utf-8', errors='replace')}"
        ) from e


def guess_base_sha() -> str:
    # Merge Request pipeline: prefer diff base sha
    mr_base = os.environ.get("CI_MERGE_REQUEST_DIFF_BASE_SHA", "").strip()
    if mr_base and mr_base != "0" * 40:
        return mr_base

    before = os.environ.get("CI_COMMIT_BEFORE_SHA", "").strip()
    if before and before != "0" * 40:
        return before

    # Fallback: previous commit
    return _run_git(["rev-parse", "HEAD~1"]).strip()


def get_head_sha() -> str:
    sha = os.environ.get("CI_COMMIT_SHA", "").strip()
    if sha and sha != "0" * 40:
        return sha
    return _run_git(["rev-parse", "HEAD"]).strip()


def diff_name_status(
    base: str, head: str = "HEAD", repo_root: Optional[Path] = None
) -> List[ChangedPath]:
    """Return list of ChangedPath, including deletions and renames."""
    out = _run_git(["diff", "--name-status", f"{base}", f"{head}"], cwd=repo_root)
    changes: List[ChangedPath] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            old_p = Path(parts[1])
            new_p = Path(parts[2])
            changes.append(ChangedPath(status=status, path=new_p, old_path=old_p))
        elif len(parts) >= 2:
            changes.append(ChangedPath(status=status, path=Path(parts[1])))
    return changes


def show_file_at(ref: str, path: Path, repo_root: Optional[Path] = None) -> str:
    """Get file contents at git ref. Useful for deleted files."""
    # Need to use POSIX path for git
    p = path.as_posix()
    return _run_git(["show", f"{ref}:{p}"], cwd=repo_root)
