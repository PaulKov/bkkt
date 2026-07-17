from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from ...models import RepoConfig
from ...ports.filesystem import FileSystem
from .models import ConnectorDirInfo, RenamePlanItem
from .naming import suggest_connector_dir_name


def _iter_domain_dirs(cfg: RepoConfig, fs: FileSystem) -> Iterable[Path]:
    root = cfg.connectors_root
    ignore = set(cfg.ignore_dirs)
    for p in fs.iterdir(root):
        if not fs.is_dir(p):
            continue
        name = Path(p).name
        if name.startswith("."):
            continue
        if name in ignore:
            continue
        yield Path(p)


def scan_connector_dirs(
    cfg: RepoConfig,
    fs: FileSystem,
    *,
    limit_to_paths: Optional[Sequence[Path]] = None,
) -> List[ConnectorDirInfo]:
    """Scan repo for connector_dir folders (domain/type/system/connector_dir)."""

    rel_filter: Optional[set[str]] = None
    if limit_to_paths:
        rel_filter = set()
        root_abs = cfg.connectors_root.resolve()
        for p in limit_to_paths:
            pp = Path(p)
            if pp.is_absolute():
                try:
                    rel = pp.resolve().relative_to(root_abs)
                except Exception:
                    rel = pp
            else:
                rel = pp
            rel_filter.add(rel.as_posix().rstrip("/"))

    root = cfg.connectors_root
    ignore = set(cfg.ignore_dirs)
    special = {"types", "modes"}

    out: List[ConnectorDirInfo] = []

    for domain_dir in _iter_domain_dirs(cfg, fs):
        domain = domain_dir.name

        for connector_type in ("source", "sink"):
            tdir = domain_dir / connector_type
            if not fs.is_dir(tdir):
                continue

            for system_dir in fs.iterdir(tdir):
                if not fs.is_dir(system_dir):
                    continue
                system = Path(system_dir).name

                for child in fs.iterdir(system_dir):
                    if not fs.is_dir(child):
                        continue

                    name = Path(child).name
                    if name.startswith("."):
                        continue
                    if name in ignore:
                        continue
                    if name in special:
                        continue

                    # Scope filter: only selected connector dirs
                    if rel_filter is not None:
                        try:
                            rel_child = Path(child).relative_to(root).as_posix()
                        except Exception:
                            rel_child = Path(child).as_posix()
                        if rel_child not in rel_filter:
                            continue

                    try:
                        rel_path = Path(child).relative_to(root)
                    except Exception:
                        rel_path = Path(child)

                    try:
                        abs_path = Path(child).resolve()
                    except Exception:
                        abs_path = Path(child)

                    out.append(
                        ConnectorDirInfo(
                            domain=domain,
                            connector_type=connector_type,
                            system=system,
                            name=name,
                            rel_path=rel_path,
                            abs_path=abs_path,
                        )
                    )

    out.sort(key=lambda x: x.rel_path.as_posix())
    return out


def build_migration_plan(
    cfg: RepoConfig,
    fs: FileSystem,
    dirs: Sequence[ConnectorDirInfo],
) -> List[RenamePlanItem]:
    """Build rename suggestions for non-standard connector_dir folders."""

    plan: List[RenamePlanItem] = []

    for info in dirs:
        suggested, reason, manual = suggest_connector_dir_name(info.domain, info.name)
        if suggested is None and not manual:
            # valid -> no action
            continue

        suggested_rel: Optional[Path] = None
        conflict = False
        conflict_with: Optional[Path] = None

        if suggested and not manual:
            suggested_rel = info.rel_path.parent / suggested
            conflict_with = cfg.connectors_root / suggested_rel
            conflict = fs.exists(conflict_with)

        plan.append(
            RenamePlanItem(
                info=info,
                suggested_name=suggested,
                suggested_rel_path=suggested_rel,
                reason=reason,
                conflict=conflict,
                conflict_with=conflict_with if conflict else None,
                manual=manual,
            )
        )

    return plan
