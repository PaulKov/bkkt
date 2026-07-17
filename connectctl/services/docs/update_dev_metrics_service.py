from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

from ...app.context import CliContext
from ...exceptions import ValidationError
from ...logging_utils import get_logger
from ...metrics.import_graph import collect_internal_deps, compute_coupling_stats
from ...metrics.loc import calc_loc_stats, is_test_python_file, iter_py_files
from ...metrics.render import build_metrics_block_md


MD_START = "<!-- BKKT_DEV_METRICS_START -->"
MD_END = "<!-- BKKT_DEV_METRICS_END -->"


@dataclass(frozen=True)
class GeneratedDoc:
    path: Path
    content: str


def _replace_block(existing: str, *, start: str, end: str, new_block: str) -> str:
    """Replace a generated block between markers, or append it if missing."""

    if start in existing and end in existing:
        before = existing.split(start)[0]
        after = existing.split(end, 1)[1]
        return before + new_block + after
    if not existing.endswith("\n"):
        existing += "\n"
    return existing + "\n" + new_block


class UpdateDevMetricsService:
    """Update generated engineering metrics docs."""

    def __init__(self, *, ctx: CliContext, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)

    def run(self, args: argparse.Namespace) -> int:
        docs_dir = Path(str(getattr(args, "docs_dir", "docs") or "docs"))
        target = str(getattr(args, "target", "all") or "all").strip().lower()
        check = bool(getattr(args, "check", False))
        top_n = int(getattr(args, "top", 15) or 15)
        if top_n < 0:
            raise ValidationError("--top must be >= 0")

        root = self.ctx.repo_root
        connectctl_dir = (root / "connectctl").resolve()
        if not connectctl_dir.exists():
            raise ValidationError(
                "connectctl/ directory was not found in the repo root"
            )

        repo_py = list(iter_py_files(root))
        repo_non_test_py = [p for p in repo_py if not is_test_python_file(p)]
        connectctl_py = list(iter_py_files(connectctl_dir))

        repo_loc = calc_loc_stats(repo_py, root=root, top_n=top_n)
        repo_non_test_loc = calc_loc_stats(repo_non_test_py, root=root, top_n=top_n)
        connectctl_loc = calc_loc_stats(connectctl_py, root=root, top_n=top_n)

        deps_out = collect_internal_deps(connectctl_dir, module_files=connectctl_py)
        coupling = compute_coupling_stats(deps_out, top_n=max(5, min(20, top_n)))

        def build_md() -> str:
            return build_metrics_block_md(
                start_marker=MD_START,
                end_marker=MD_END,
                repo_loc=repo_loc,
                repo_non_test_loc=repo_non_test_loc,
                connectctl_loc=connectctl_loc,
                coupling=coupling,
            )

        docs: List[GeneratedDoc] = []
        if target in {"all", "md", "markdown"}:
            docs.append(
                self._update_one(
                    path=(root / docs_dir / "ENGINEERING_METRICS.md").resolve(),
                    build_block=build_md,
                )
            )

        if not docs:
            raise ValidationError(f"Unknown target={target!r}. Expected one of: all|md")

        mismatched: List[Path] = []
        for d in docs:
            if check:
                if not self.ctx.fs.exists(d.path):
                    mismatched.append(d.path)
                    continue
                if self.ctx.fs.read_text(d.path) != d.content:
                    mismatched.append(d.path)
            else:
                self.ctx.fs.mkdirs(d.path.parent, exist_ok=True)
                self.ctx.fs.write_text(d.path, d.content)

        if check:
            if mismatched:
                self.log.error(
                    "Engineering metrics docs are out of date (%s). Run: bkkt docs update-dev-metrics",
                    ", ".join(str(p) for p in mismatched),
                )
                return 2
            self.log.info("Engineering metrics docs are up to date.")
            return 0

        for d in docs:
            self.log.info("✅ Updated engineering metrics doc: %s", d.path.as_posix())
        return 0

    def _update_one(
        self, *, path: Path, build_block: Callable[[], str]
    ) -> GeneratedDoc:
        if not self.ctx.fs.exists(path):
            raise ValidationError(f"Не найден файл документации: {path}")
        existing = self.ctx.fs.read_text(path)
        block = build_block()
        content = _replace_block(existing, start=MD_START, end=MD_END, new_block=block)
        return GeneratedDoc(path=path, content=content)
