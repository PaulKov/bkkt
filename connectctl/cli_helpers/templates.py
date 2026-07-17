from __future__ import annotations

from pathlib import Path

from ..logging_utils import get_logger
from ..repo.apply_targets import ApplyTargets


def _print_template_expansions(
    targets: ApplyTargets, repo_root: Path, *, logger=None
) -> None:
    """Log template expansion events (generated paths, skipped existing)."""
    log = get_logger(logger)
    if not targets.expansions:
        return

    log.info("Template expansion:")
    for ev in targets.expansions:
        try:
            tpl_rel = ev.template_path.relative_to(repo_root).as_posix()
        except Exception:
            tpl_rel = str(ev.template_path)
        log.info("  %s", tpl_rel)

        for g in ev.generated:
            try:
                g_rel = g.relative_to(repo_root).as_posix()
            except Exception:
                g_rel = str(g)
            log.info("    -> %s  [%s]", g_rel, ev.source)

        for s in ev.skipped_existing:
            try:
                s_rel = s.relative_to(repo_root).as_posix()
            except Exception:
                s_rel = str(s)
            log.info("    (skipped: exists) %s", s_rel)
