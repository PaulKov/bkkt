from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence, Set, Tuple

from ...models import RepoConfig
from ...ports.filesystem import FileSystem
from .models import ReferenceUpdateResult, RenamePlanItem


_TEXT_EXTS = {
    ".md",
    ".markdown",
    ".yml",
    ".yaml",
    ".txt",
    ".sh",
    ".py",
    ".toml",
    ".json",
    ".ini",
    ".cfg",
}


def _is_text_file(p: Path) -> bool:
    if p.suffix.lower() in _TEXT_EXTS:
        return True
    return False


def _iter_files_by_globs(
    fs: FileSystem, root: Path, patterns: Sequence[str]
) -> Iterable[Path]:
    seen: Set[str] = set()
    for pat in patterns:
        for p in fs.glob(root, pat):
            pp = Path(p)
            key = pp.as_posix()
            if key in seen:
                continue
            seen.add(key)
            yield pp


def _resolve_reference_globs(scope_tokens: Sequence[str]) -> List[str]:
    # Default safe scope: docs + ci (and root configs).
    tokens = [t.strip().lower() for t in scope_tokens if t and t.strip()]
    if not tokens:
        tokens = ["docs", "ci"]

    if "all" in tokens:
        return [
            "README.md",
            "docs/**/*",
            "ci/**/*",
            ".vscode/**/*",
            "**/*.md",
            "**/*.yml",
            "**/*.yaml",
            "**/*.sh",
            "**/*.py",
            "**/*.toml",
            "**/*.json",
        ]

    globs: List[str] = ["README.md"]
    if "docs" in tokens:
        globs.append("docs/**/*")
    if "ci" in tokens:
        globs.append("ci/**/*")
    if "vscode" in tokens:
        globs.append(".vscode/**/*")
    return globs


def update_references(
    cfg: RepoConfig,
    fs: FileSystem,
    *,
    renames: Sequence[RenamePlanItem],
    scope_tokens: Sequence[str],
    max_touched_paths: int = 20,
) -> ReferenceUpdateResult:
    """Update textual references to old connector_dir paths.

    Safety:
    - We replace only full relative paths (from repo root) of renamed directories.
    - We only touch typical text file types.
    - Default scope is docs+ci plus README.

    Returns number of updated files and up to max_touched_paths file paths.
    """

    # Prepare replacements: old_rel -> new_rel
    replacements: List[Tuple[str, str]] = []
    for it in renames:
        if not it.suggested_rel_path:
            continue
        old_abs = cfg.connectors_root / it.info.rel_path
        new_abs = cfg.connectors_root / it.suggested_rel_path
        try:
            old_rel = old_abs.relative_to(cfg.root).as_posix()
        except Exception:
            old_rel = old_abs.as_posix()
        try:
            new_rel = new_abs.relative_to(cfg.root).as_posix()
        except Exception:
            new_rel = new_abs.as_posix()
        replacements.append((old_rel, new_rel))

    if not replacements:
        return ReferenceUpdateResult(updated_files=0, touched_paths=[])

    patterns = _resolve_reference_globs(scope_tokens)

    updated_files = 0
    touched: List[str] = []

    for p in _iter_files_by_globs(fs, cfg.root, patterns):
        if not _is_text_file(p):
            continue
        if not fs.is_file(p):
            continue

        try:
            raw = fs.read_text(p)
        except Exception:
            # skip unreadable files
            continue

        updated = raw
        changed = False
        for old, new in replacements:
            if old in updated:
                updated = updated.replace(old, new)
                changed = True

        if changed and updated != raw:
            fs.write_text(p, updated)
            updated_files += 1
            if len(touched) < max_touched_paths:
                try:
                    touched.append(str(p.relative_to(cfg.root)))
                except Exception:
                    touched.append(str(p))

    return ReferenceUpdateResult(updated_files=updated_files, touched_paths=touched)
