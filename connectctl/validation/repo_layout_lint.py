from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence

from ..models import RepoConfig
from .repo_layout_models import CONNECTOR_DIR_DATASET_RE, RepoLayoutIssue
from .repo_layout_scan import iter_domain_dirs


def lint_connector_dir_pattern(
    cfg: RepoConfig,
    *,
    check_dataset_charset: bool = True,
    limit_to_paths: Optional[Sequence[Path]] = None,
) -> List[RepoLayoutIssue]:
    """Repo-wide lint: validate that connector_dir follows the standard template.

    Expected directory name:
      connector_<domain>__<dataset>{__<optional_suffix>}

    Where:
      - <domain> must match the top-level domain folder name
      - <dataset> is a non-empty token; by default we also check it looks like a slug
        (letters/digits/underscore). This can be disabled via check_dataset_charset=False.

    Notes:
      - This is intentionally a *repo-wide* lint: it scans directory names, not manifests.
      - Special system-level folders like "types", "modes", and "sql" are ignored.
    """

    issues: List[RepoLayoutIssue] = []

    # Optional scope filter.
    #
    # When set, we only validate connector directories whose relative path (from
    # connectors_root) is present in this filter. This is used in CI together
    # with validate --changed, to avoid flooding logs with historical/legacy
    # violations in unrelated domains.
    rel_filter: Optional[set[str]] = None
    if limit_to_paths:
        rel_filter = set()
        root_abs = cfg.connectors_root.resolve()
        for p in limit_to_paths:
            pp = Path(p)
            # Normalize absolute paths to be relative to connectors_root.
            if pp.is_absolute():
                try:
                    rel = pp.resolve().relative_to(root_abs)
                except Exception:
                    # Best-effort: fall back to the provided path.
                    rel = pp
            else:
                rel = pp
            rel_filter.add(rel.as_posix().rstrip("/"))

    root = cfg.connectors_root
    ignore = set(cfg.ignore_dirs)
    special = {"types", "modes", "sql"}

    for domain_dir in iter_domain_dirs(cfg):
        domain = domain_dir.name

        for connector_type in ("source", "sink"):
            tdir = domain_dir / connector_type
            if not tdir.is_dir():
                continue

            for system_dir in tdir.iterdir():
                if not system_dir.is_dir():
                    continue
                system = system_dir.name

                for child in system_dir.iterdir():
                    if not child.is_dir():
                        continue
                    # Scope filter: only check selected connector dirs.
                    if rel_filter is not None:
                        try:
                            rel_child = child.relative_to(root).as_posix()
                        except Exception:
                            rel_child = child.as_posix()
                        if rel_child not in rel_filter:
                            continue

                    name = child.name
                    if name.startswith("."):
                        continue
                    if name in ignore:
                        continue
                    if name in special:
                        continue

                    # Check: connector_<domain>__...
                    expected_prefix = f"connector_{domain}__"
                    if not name.startswith("connector_"):
                        # Non-standard folder at connector level (still a lint finding)
                        issues.append(
                            RepoLayoutIssue(
                                severity="warn",
                                policy="CONNECTOR_DIR_PATTERN",
                                domain=domain,
                                connector_type=connector_type,
                                system=system,
                                connector_dir=name,
                                path=str(child.relative_to(root)),
                                message=(
                                    "Каталог коннектора не начинается с 'connector_'. "
                                    "Ожидается: connector_<domain>__<dataset>{__<optional_suffix>}"
                                ),
                                hint=f"Пример: connector_{domain}__<dataset>",
                            )
                        )
                        continue

                    if not name.startswith(expected_prefix):
                        issues.append(
                            RepoLayoutIssue(
                                severity="warn",
                                policy="CONNECTOR_DIR_PATTERN",
                                domain=domain,
                                connector_type=connector_type,
                                system=system,
                                connector_dir=name,
                                path=str(child.relative_to(root)),
                                message=(
                                    "Каталог коннектора не соответствует шаблону для данного домена. "
                                    f"Ожидается префикс: {expected_prefix}"
                                ),
                                hint=f"Переименуйте в: connector_{domain}__<dataset>{{__<optional_suffix>}}",
                            )
                        )
                        continue

                    rest = name[len(expected_prefix) :]
                    if not rest or rest.startswith("__"):
                        issues.append(
                            RepoLayoutIssue(
                                severity="warn",
                                policy="CONNECTOR_DIR_PATTERN",
                                domain=domain,
                                connector_type=connector_type,
                                system=system,
                                connector_dir=name,
                                path=str(child.relative_to(root)),
                                message=(
                                    "В имени connector_dir отсутствует <dataset> (пустой сегмент после '__'). "
                                    "Ожидается: connector_<domain>__<dataset>{__<optional_suffix>}"
                                ),
                                hint=f"Пример: connector_{domain}__payments",
                            )
                        )
                        continue

                    dataset = rest.split("__", 1)[0]
                    if check_dataset_charset and not CONNECTOR_DIR_DATASET_RE.match(
                        dataset
                    ):
                        issues.append(
                            RepoLayoutIssue(
                                severity="warn",
                                policy="CONNECTOR_DIR_PATTERN",
                                domain=domain,
                                connector_type=connector_type,
                                system=system,
                                connector_dir=name,
                                path=str(child.relative_to(root)),
                                message=(
                                    "Сегмент <dataset> в connector_dir содержит неожиданные символы. "
                                    "Рекомендуется использовать только буквы/цифры/underscore."
                                ),
                                hint=(
                                    "Рекомендуемый формат: connector_<domain>__<dataset>{__<optional_suffix>}, "
                                    f"например connector_{domain}__payments"
                                ),
                            )
                        )

    return issues
