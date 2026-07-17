from __future__ import annotations

import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import List, Optional, Sequence

from ...exceptions import ConfigError
from ...logging_utils import get_logger
from ...ports import FileSystem


@dataclass(frozen=True)
class BootstrapAction:
    action: str  # create|overwrite|skip
    path: Path


@dataclass(frozen=True)
class RepoBootstrapResult:
    created: int
    overwritten: int
    dist_created: int
    dist_overwritten: int
    skipped: int
    actions: Sequence[BootstrapAction]


class RepoBootstrapService:
    """Create helper directories in a manifests repository.

    Command: `bkkt repo bootstrap`
    """

    def __init__(self, *, ctx, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or getattr(ctx, "logger", None))

    def run(self, args) -> int:
        repo_root = Path(getattr(self.ctx, "repo_root", ".")).resolve()
        fs: FileSystem = getattr(self.ctx, "fs")

        preset = str(getattr(args, "preset", "full") or "full").strip().lower()
        if preset not in {"full", "minimal"}:
            raise ConfigError("--preset must be one of: full|minimal")

        force = bool(getattr(args, "force", False))
        update = bool(getattr(args, "update", False))
        dry_run = bool(getattr(args, "dry_run", False))

        if force and update:
            raise ConfigError("Нельзя использовать одновременно --force и --update")

        only_raw = getattr(args, "only", None)
        only: Optional[List[str]] = (
            [str(x) for x in (only_raw or [])] if only_raw else None
        )

        selected = self._resolve_selected_sections(only)

        # Destination for init templates can be overridden via env var as well.
        init_templates_root = (
            str(getattr(args, "init_templates_root", "") or "").strip() or None
        )
        if init_templates_root is None:
            init_templates_root = (
                str(os.getenv("BKKT_INIT_TEMPLATES_ROOT", "__init_templates")).strip()
                or "__init_templates"
            )

        section_to_dest = {
            "connectctl": repo_root / "connectctl.yaml",
            "global": repo_root / "__global",
            "init-templates": repo_root / init_templates_root,
            "schemas": repo_root / "schemas",
        }

        if preset == "minimal":
            res = self._bootstrap_minimal(
                fs=fs,
                selected=selected,
                section_to_dest=section_to_dest,
                force=force,
                update=update,
                dry_run=dry_run,
            )
        else:
            res = self._bootstrap_full(
                fs=fs,
                selected=selected,
                section_to_dest=section_to_dest,
                force=force,
                update=update,
                dry_run=dry_run,
            )

        self._print_summary(res, dry_run=dry_run)
        return 0

    def _resolve_selected_sections(self, only: Optional[List[str]]) -> List[str]:
        if only is None:
            # Default UX: create a minimal starter repo.
            return ["connectctl", "global", "init-templates"]

        normalized = [x.strip().lower() for x in only if str(x).strip()]
        allowed = {"connectctl", "global", "init-templates", "schemas"}
        unknown = [x for x in normalized if x not in allowed]
        if unknown:
            raise ConfigError(
                f"Unknown value for --only: {unknown}. Allowed: {sorted(allowed)}"
            )

        # Deduplicate while keeping order.
        seen = set()
        out: list[str] = []
        for x in normalized:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    def _bootstrap_minimal(
        self,
        *,
        fs: FileSystem,
        selected: Sequence[str],
        section_to_dest: dict,
        force: bool,
        update: bool,
        dry_run: bool,
    ) -> RepoBootstrapResult:
        actions: list[BootstrapAction] = []
        created = overwritten = skipped = 0
        dist_created = dist_overwritten = 0

        for section in selected:
            dest_root = section_to_dest[section]
            if section == "connectctl":
                payload = (
                    "version: 1\n"
                    "connectors_root: .\n"
                    "ignore_dirs:\n"
                    "  - .git\n"
                    "  - .cache\n"
                    "  - .vscode\n"
                    "  - .idea\n"
                    "  - docs\n"
                    "  - __global\n"
                    "  - __init_templates\n"
                    "  - schemas\n"
                    "default_cluster: default\n"
                    "clusters:\n"
                    "  default:\n"
                    "    dev:\n"
                    "      connect:\n"
                    "        scheme: http\n"
                    "        port: 8083\n"
                    '        hosts: ["127.0.0.1"]\n'
                    "naming:\n"
                    "  enabled: true\n"
                    "  strict: true\n"
                    "  rules:\n"
                    "    - id: source_default\n"
                    "      applies_to:\n"
                    "        type: [source]\n"
                    "      template: '{env}.{domain}.{dataset}.source.{system}.{index}'\n"
                    "    - id: sink_default\n"
                    "      applies_to:\n"
                    "        type: [sink]\n"
                    "      template: '{env}.{domain}.{dataset}.sink.{layer}.{system}.{index}'\n"
                    "sync:\n"
                    "  prune:\n"
                    "    allow_regex: ['^{env}\\\\.']\n"
                    "    deny_regex: ['^_']\n"
                    "safety:\n"
                    "  direct_put:\n"
                    "    enabled: false\n"
                )
                exists_before = fs.exists(dest_root)
                if exists_before and not force:
                    if update:
                        try:
                            old = fs.read_text(dest_root)
                        except Exception:
                            old = ""
                        if old != payload:
                            dist_path = Path(str(dest_root) + ".bkkt.dist")
                            dist_exists = fs.exists(dist_path)
                            if not dry_run:
                                fs.write_text(dist_path, payload)
                            actions.append(
                                BootstrapAction(
                                    action=(
                                        "dist-overwrite"
                                        if dist_exists
                                        else "dist-create"
                                    ),
                                    path=dist_path,
                                )
                            )
                            if dist_exists:
                                dist_overwritten += 1
                            else:
                                dist_created += 1
                        else:
                            actions.append(
                                BootstrapAction(action="skip", path=dest_root)
                            )
                            skipped += 1
                    else:
                        actions.append(BootstrapAction(action="skip", path=dest_root))
                        skipped += 1
                    continue

                if not dry_run:
                    fs.write_text(dest_root, payload)

                actions.append(
                    BootstrapAction(
                        action="overwrite" if exists_before else "create",
                        path=dest_root,
                    )
                )
                if exists_before:
                    overwritten += 1
                else:
                    created += 1
                continue

            dest_root = Path(dest_root)
            if not dry_run:
                fs.mkdirs(dest_root, exist_ok=True)
            actions.append(BootstrapAction(action="create", path=dest_root))

            # Add a small README to make the directory self-explanatory.
            if section == "global":
                readme = dest_root / "README.md"
                payload = (
                    "# __global\n\n"
                    "Layered overrides for BKKT.\n\n"
                    "See: docs/ROUTING.md and README.md.\n"
                )
            elif section == "init-templates":
                readme = dest_root / "README.md"
                payload = (
                    "# __init_templates\n\n"
                    "Init templates for `bkkt init`.\n\n"
                    "See: docs/INIT.md\n"
                )
            else:
                readme = dest_root / "README.md"
                payload = (
                    "# schemas\n\n" "JSON Schemas for `bkkt validate` and IDE hints.\n"
                )

            exists_before = fs.exists(readme)

            if exists_before and not force:
                if update:
                    # Write a .bkkt.dist neighbor file if content differs.
                    try:
                        old = fs.read_text(readme)
                    except Exception:
                        old = ""
                    if old != payload:
                        dist_path = Path(str(readme) + ".bkkt.dist")
                        dist_exists = fs.exists(dist_path)
                        if not dry_run:
                            fs.write_text(dist_path, payload)
                        actions.append(
                            BootstrapAction(
                                action=(
                                    "dist-overwrite" if dist_exists else "dist-create"
                                ),
                                path=dist_path,
                            )
                        )
                        if dist_exists:
                            dist_overwritten += 1
                        else:
                            dist_created += 1
                    else:
                        actions.append(BootstrapAction(action="skip", path=readme))
                        skipped += 1
                else:
                    actions.append(BootstrapAction(action="skip", path=readme))
                    skipped += 1
                continue

            if not dry_run:
                fs.write_text(readme, payload)

            actions.append(
                BootstrapAction(
                    action="overwrite" if exists_before else "create", path=readme
                )
            )
            if exists_before:
                overwritten += 1
            else:
                created += 1

        return RepoBootstrapResult(
            created=created,
            overwritten=overwritten,
            dist_created=dist_created,
            dist_overwritten=dist_overwritten,
            skipped=skipped,
            actions=actions,
        )

    def _bootstrap_full(
        self,
        *,
        fs: FileSystem,
        selected: Sequence[str],
        section_to_dest: dict,
        force: bool,
        update: bool,
        dry_run: bool,
    ) -> RepoBootstrapResult:
        actions: list[BootstrapAction] = []
        created = overwritten = skipped = 0
        dist_created = dist_overwritten = 0

        try:
            pkg_root = resources.files("connectctl.assets.repo_defaults")
        except Exception as e:
            # Should never happen in source tree, but may happen if packaging excludes data.
            self.log.warning(
                "Repo defaults assets are not available (%s). Falling back to --preset minimal.",
                e,
            )
            return self._bootstrap_minimal(
                fs=fs,
                selected=selected,
                section_to_dest=section_to_dest,
                force=force,
                update=update,
                dry_run=dry_run,
            )

        with resources.as_file(pkg_root) as defaults_root:
            defaults_root = Path(defaults_root)
            for section in selected:
                src_name = {
                    "connectctl": "connectctl.yaml",
                    "global": "__global",
                    "init-templates": "__init_templates",
                    "schemas": "schemas",
                }[section]

                src_path = defaults_root / src_name
                if section == "connectctl":
                    if not src_path.exists() or not src_path.is_file():
                        self.log.warning(
                            "Defaults for section %s not found at %s", section, src_path
                        )
                        continue

                    c, o, s, acts = self._copy_file(
                        fs=fs,
                        src_file=src_path,
                        dest_file=Path(section_to_dest[section]),
                        force=force,
                        update=update,
                        dry_run=dry_run,
                    )
                else:
                    if not src_path.exists() or not src_path.is_dir():
                        self.log.warning(
                            "Defaults for section %s not found at %s", section, src_path
                        )
                        continue

                    c, o, s, acts = self._copy_tree(
                        fs=fs,
                        src_dir=src_path,
                        dest_dir=Path(section_to_dest[section]),
                        force=force,
                        update=update,
                        dry_run=dry_run,
                    )
                created += c
                overwritten += o
                skipped += s
                actions.extend(acts)

        # dist counts are encoded in actions for now.
        for a in actions:
            if a.action == "dist-create":
                dist_created += 1
            elif a.action == "dist-overwrite":
                dist_overwritten += 1

        return RepoBootstrapResult(
            created=created,
            overwritten=overwritten,
            dist_created=dist_created,
            dist_overwritten=dist_overwritten,
            skipped=skipped,
            actions=actions,
        )

    def _copy_tree(
        self,
        *,
        fs: FileSystem,
        src_dir: Path,
        dest_dir: Path,
        force: bool,
        update: bool,
        dry_run: bool,
    ) -> tuple[int, int, int, List[BootstrapAction]]:
        """Copy a directory tree from local FS (package assets) to target repo via FileSystem."""

        actions: list[BootstrapAction] = []
        created = overwritten = skipped = 0

        if not dry_run:
            fs.mkdirs(dest_dir, exist_ok=True)

        # Iterate over both files and dirs.
        for p in sorted(src_dir.rglob("*")):
            rel = p.relative_to(src_dir)
            out = dest_dir / rel
            if p.is_dir():
                if not dry_run:
                    fs.mkdirs(out, exist_ok=True)
                continue

            # Only text resources are supported in the default skeleton.
            try:
                data = p.read_text(encoding="utf-8")
            except Exception as e:
                self.log.warning("Skip non-text resource %s: %s", p, e)
                continue

            exists = fs.exists(out)
            if exists and not force:
                if update:
                    try:
                        old = fs.read_text(out)
                    except Exception:
                        old = ""
                    if old != data:
                        dist_path = Path(str(out) + ".bkkt.dist")
                        dist_exists = fs.exists(dist_path)
                        if not dry_run:
                            fs.write_text(dist_path, data)
                        actions.append(
                            BootstrapAction(
                                action=(
                                    "dist-overwrite" if dist_exists else "dist-create"
                                ),
                                path=dist_path,
                            )
                        )
                    else:
                        actions.append(BootstrapAction(action="skip", path=out))
                        skipped += 1
                else:
                    actions.append(BootstrapAction(action="skip", path=out))
                    skipped += 1
                continue

            if not dry_run:
                fs.write_text(out, data)

            if exists:
                actions.append(BootstrapAction(action="overwrite", path=out))
                overwritten += 1
            else:
                actions.append(BootstrapAction(action="create", path=out))
                created += 1

        return created, overwritten, skipped, actions

    def _copy_file(
        self,
        *,
        fs: FileSystem,
        src_file: Path,
        dest_file: Path,
        force: bool,
        update: bool,
        dry_run: bool,
    ) -> tuple[int, int, int, List[BootstrapAction]]:
        actions: list[BootstrapAction] = []
        created = overwritten = skipped = 0

        try:
            data = src_file.read_text(encoding="utf-8")
        except Exception as e:
            self.log.warning("Skip non-text resource %s: %s", src_file, e)
            return created, overwritten, skipped, actions

        exists = fs.exists(dest_file)
        if exists and not force:
            if update:
                try:
                    old = fs.read_text(dest_file)
                except Exception:
                    old = ""
                if old != data:
                    dist_path = Path(str(dest_file) + ".bkkt.dist")
                    dist_exists = fs.exists(dist_path)
                    if not dry_run:
                        fs.write_text(dist_path, data)
                    actions.append(
                        BootstrapAction(
                            action=("dist-overwrite" if dist_exists else "dist-create"),
                            path=dist_path,
                        )
                    )
                else:
                    actions.append(BootstrapAction(action="skip", path=dest_file))
                    skipped += 1
            else:
                actions.append(BootstrapAction(action="skip", path=dest_file))
                skipped += 1
            return created, overwritten, skipped, actions

        if not dry_run:
            fs.write_text(dest_file, data)

        if exists:
            actions.append(BootstrapAction(action="overwrite", path=dest_file))
            overwritten += 1
        else:
            actions.append(BootstrapAction(action="create", path=dest_file))
            created += 1

        return created, overwritten, skipped, actions

    def _print_summary(self, res: RepoBootstrapResult, *, dry_run: bool) -> None:
        verb = "PLAN" if dry_run else "DONE"
        self.log.info(
            "repo bootstrap %s: created=%s overwritten=%s dist_created=%s dist_overwritten=%s skipped=%s",
            verb,
            res.created,
            res.overwritten,
            res.dist_created,
            res.dist_overwritten,
            res.skipped,
        )

        # Print a small sample of actions (keep output readable).
        max_lines = 30
        for a in list(res.actions)[:max_lines]:
            self.log.info("  %s: %s", a.action.upper(), a.path)
        if len(res.actions) > max_lines:
            self.log.info("  … and %s more", len(res.actions) - max_lines)
