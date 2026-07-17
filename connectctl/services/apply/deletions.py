from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Sequence

from ...git import guess_base_sha, show_file_at
from ...git_changes import render_for_deleted_path
from ...logging_utils import get_logger
from ...ports import ConnectApi
from ...routing_router import ClusterRouter
from ...settings import Settings


def apply_deletions(
    *,
    delete_rels: Iterable[Path],
    repo_root: Path,
    base_ref: Optional[str],
    settings: Settings,
    router: ClusterRouter,
    get_connect: Callable[[str], ConnectApi],
    renderer: Any,
    runtime_vars: Dict[str, Any],
    runtime_var_sources: Dict[str, str],
    reuse_overrides: bool,
    reuse_from: Optional[Sequence[Path]],
    dry_run: bool,
    logger=None,
) -> None:
    """
    Handle deletions from `--changed` plan (desired-state).

    Important: in multi-cluster setups we must delete from the *same* cluster group
    where the connector would have been applied. We determine it via routing.
    """

    log = get_logger(logger)

    rels = list(delete_rels)
    if not rels:
        return

    base = base_ref or guess_base_sha()

    for rel in rels:
        abs_path = (repo_root / rel).resolve()

        # We need the connector name (and routing metadata). For deleted files, load the content
        # from base_ref, write it temporarily under repo_root and run the regular renderer.
        tmp_written = False
        try:
            try:
                # Для удалённых файлов получаем содержимое из git по ref и относительному пути.
                content = show_file_at(base, rel, repo_root=repo_root)
            except Exception as e:
                log.warning(
                    "Cannot read deleted file content from %s for %s: %s", base, rel, e
                )
                content = None

            name: Optional[str] = None
            cluster_name: Optional[str] = None

            if content is not None:
                if abs_path.exists():
                    # Safety: do not overwrite if something exists there (rename edge case)
                    log.warning(
                        "Skip deletion routing render for %s: path exists in working tree",
                        rel,
                    )
                else:
                    abs_path.parent.mkdir(parents=True, exist_ok=True)
                    abs_path.write_text(content, encoding="utf-8")
                    tmp_written = True

                    rr = renderer.render(
                        abs_path,
                        runtime_vars=runtime_vars,
                        runtime_var_sources=runtime_var_sources,
                        reuse_overrides=reuse_overrides,
                        reuse_from=list(reuse_from) if reuse_from else None,
                    )
                    name_mn: str = rr.manifest.name
                    name = name_mn
                    decision, _ = router.route_with_debug(
                        connector_name=name_mn,
                        connectctl_meta=rr.connectctl,
                        connectctl_sources=rr.connectctl_sources,
                    )
                    cluster_name = decision.cluster.name

            if name is None:
                # Fallback: best-effort name extraction (without full routing metadata)
                try:
                    name = render_for_deleted_path(
                        repo_root=repo_root,
                        base_ref=base,
                        relpath=rel,
                        settings=settings,
                    )
                except Exception as e:
                    log.warning(
                        "Cannot determine connector name for deleted file %s: %s",
                        rel,
                        e,
                    )
                    continue

            if cluster_name is None:
                decision, _ = router.route_with_debug(
                    connector_name=name,
                    connectctl_meta={},
                    connectctl_sources={},
                )
                cluster_name = decision.cluster.name

            if dry_run:
                log.info(
                    "[DRY-RUN] Would delete connector: %s (cluster=%s) (because %s was deleted)",
                    name,
                    cluster_name,
                    rel,
                )
            else:
                log.info(
                    "Deleting connector: %s (cluster=%s) (because %s was deleted)",
                    name,
                    cluster_name,
                    rel,
                )
                connect = get_connect(cluster_name)
                connect.delete(name)

        finally:
            if tmp_written:
                try:
                    abs_path.unlink()
                except Exception:
                    pass
