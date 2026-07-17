from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from ...app.context import CliContext
from ...exceptions import ConfigError
from ...git import diff_name_status, get_head_sha, guess_base_sha
from ...logging_utils import get_logger
from ...output import (
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
)
from ...repo.connector_dir_scope import infer_connector_dir_scope_from_path
from .models import MigrationResult, RenamePlanItem
from .references import update_references
from .scanner import build_migration_plan, scan_connector_dirs


class RepoMigrateConnectorDirService:
    """Нормализация исторических connector_dir к стандарту.

    Цель:
      - привести каталоги коннекторов к шаблону:
          connector_<domain>__<dataset>{__<optional_suffix>}
      - упростить массовую миграцию (dry-run → apply)
    """

    def __init__(self, *, ctx: CliContext, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or getattr(ctx, "logger", None))

    def _collect_changed_scope(self, args: argparse.Namespace) -> List[Path]:
        base = getattr(args, "base", None) or guess_base_sha()
        head = getattr(args, "head", None) or get_head_sha()

        try:
            changes = diff_name_status(base, head, repo_root=self.ctx.repo_root)
        except Exception as e:
            self.log.warning("Не удалось получить git diff для scope=changed: %s", e)
            return []

        scope: set[Path] = set()
        for ch in changes:
            cand = infer_connector_dir_scope_from_path(
                self.ctx.settings.repo, Path(ch.path)
            )
            if cand is not None:
                scope.add(cand)

        return sorted(scope, key=lambda x: x.as_posix())

    def _format_plan_text(self, plan: Sequence[RenamePlanItem], *, limit: int) -> str:
        total = len(plan)
        actionable = sum(
            1
            for it in plan
            if it.suggested_rel_path and not it.conflict and not it.manual
        )
        conflicts = sum(1 for it in plan if it.conflict)
        manual = sum(1 for it in plan if it.manual or not it.suggested_rel_path)

        lines: List[str] = []
        lines.append(
            f"Repo migrate connector_dir: violations={total} actionable={actionable} conflicts={conflicts} manual={manual}"
        )

        shown = plan if limit <= 0 else list(plan[:limit])
        for it in shown:
            old = it.info.rel_path.as_posix()
            if it.suggested_rel_path:
                new = it.suggested_rel_path.as_posix()
            else:
                new = "<manual>"
            flags: List[str] = []
            if it.conflict:
                flags.append("CONFLICT")
            if it.manual:
                flags.append("MANUAL")
            flag_s = f" [{' '.join(flags)}]" if flags else ""
            reason = f" ({it.reason})" if it.reason else ""
            lines.append(f" - {old} -> {new}{flag_s}{reason}")

        tail = max(0, total - len(shown))
        if tail:
            lines.append(f"… и ещё {tail}")

        return "\n".join(lines)

    def _build_payload(
        self, plan: Sequence[RenamePlanItem], result: Optional[MigrationResult]
    ) -> dict:
        items = []
        for it in plan:
            items.append(
                {
                    "old": it.info.rel_path.as_posix(),
                    "new": (
                        it.suggested_rel_path.as_posix()
                        if it.suggested_rel_path
                        else None
                    ),
                    "reason": it.reason,
                    "conflict": bool(it.conflict),
                    "manual": bool(it.manual),
                }
            )

        summary = {
            "violations": len(plan),
            "actionable": sum(
                1
                for it in plan
                if it.suggested_rel_path and not it.conflict and not it.manual
            ),
            "conflicts": sum(1 for it in plan if it.conflict),
            "manual": sum(1 for it in plan if it.manual or not it.suggested_rel_path),
        }

        payload = {"summary": summary, "items": items}
        if result is not None:
            payload["result"] = {
                "applied": result.applied,
                "skipped": result.skipped,
                "reference_updates": (
                    {
                        "updated_files": result.reference_updates.updated_files,
                        "touched_paths": result.reference_updates.touched_paths,
                    }
                    if result.reference_updates
                    else None
                ),
            }
        return payload

    def run(self, args: argparse.Namespace) -> int:
        settings = self.ctx.settings

        scope = str(getattr(args, "scope", "all") or "all").strip().lower()
        limit = int(getattr(args, "limit", 20) or 20)
        apply_changes = bool(getattr(args, "apply", False))
        dry_run = bool(getattr(args, "dry_run", False)) or (not apply_changes)
        assume_yes = bool(getattr(args, "yes", False))
        on_conflict = (
            str(getattr(args, "on_conflict", "error") or "error").strip().lower()
        )

        update_refs = bool(getattr(args, "update_references", False))
        update_refs_scope_raw = str(getattr(args, "update_references_scope", "") or "")
        update_refs_scope = [
            x.strip() for x in update_refs_scope_raw.split(",") if x.strip()
        ]
        if not update_refs_scope:
            update_refs_scope = ["docs", "ci"]

        limit_to_paths: Optional[List[Path]] = None
        if scope == "changed":
            limit_to_paths = self._collect_changed_scope(args)
            if not limit_to_paths:
                self.log.info(
                    "scope=changed: нет затронутых connector_dir по git diff."
                )
                plan: List[RenamePlanItem] = []
            else:
                dirs = scan_connector_dirs(
                    settings.repo, self.ctx.fs, limit_to_paths=limit_to_paths
                )
                plan = build_migration_plan(settings.repo, self.ctx.fs, dirs)
        else:
            dirs = scan_connector_dirs(settings.repo, self.ctx.fs)
            plan = build_migration_plan(settings.repo, self.ctx.fs, dirs)

        plan.sort(key=lambda x: x.info.rel_path.as_posix())

        output_fmt = resolve_output_format(args)
        output_text = self._format_plan_text(plan, limit=limit)

        if dry_run and not plan:
            # nothing to do
            if is_machine_output(output_fmt):
                write_payload(self._build_payload(plan, None), fmt=output_fmt)
            else:
                write_text(output_text + "\n")
            return 0

        # Always show plan in logs (stderr) for apply mode, keep stdout clean for machine output.
        self.log.info("%s", output_text)

        if dry_run:
            if is_machine_output(output_fmt):
                write_payload(self._build_payload(plan, None), fmt=output_fmt)
            else:
                write_text(output_text + "\n")
            return 0

        # apply mode
        actionable = [it for it in plan if it.suggested_rel_path and not it.manual]
        conflicts = [it for it in actionable if it.conflict]
        if conflicts and on_conflict == "error":
            raise ConfigError(
                f"Найдены конфликты путей ({len(conflicts)}). Используйте --on-conflict skip|suffix или исправьте вручную."
            )

        if not assume_yes:
            if not sys.stdin.isatty():
                raise ConfigError(
                    "Отказ: нельзя выполнять migrate без -y/--yes в неинтерактивном режиме"
                )
            ans = (
                input(f"Выполнить переименование {len(actionable)} каталогов? [y/N]: ")
                .strip()
                .lower()
            )
            if ans not in {"y", "yes"}:
                self.log.warning("Отменено.")
                return 1

        applied = 0
        skipped = 0

        def _unique_target(base_rel: Path) -> Path:
            if not self.ctx.fs.exists(settings.repo.connectors_root / base_rel):
                return base_rel
            # Add __migrated, __migrated_2...
            stem = base_rel.name
            parent = base_rel.parent
            for i in range(1, 100):
                suffix = "__migrated" if i == 1 else f"__migrated_{i}"
                cand = parent / (stem + suffix)
                if not self.ctx.fs.exists(settings.repo.connectors_root / cand):
                    return cand
            raise ConfigError(
                f"Не удалось подобрать уникальное имя для {base_rel.as_posix()}"
            )

        applied_items: List[RenamePlanItem] = []

        for it in actionable:
            if it.conflict:
                if on_conflict == "skip":
                    skipped += 1
                    continue
                if on_conflict == "suffix":
                    assert it.suggested_rel_path is not None
                    new_rel = _unique_target(it.suggested_rel_path)
                else:
                    raise ConfigError(f"Неизвестная политика конфликтов: {on_conflict}")
            else:
                new_rel = it.suggested_rel_path  # type: ignore[assignment]

            src = settings.repo.connectors_root / it.info.rel_path
            dst = settings.repo.connectors_root / new_rel
            self.ctx.fs.rename(src, dst)
            applied += 1

            # Track the actual applied target for reference updates.
            if new_rel != it.suggested_rel_path:
                applied_items.append(
                    RenamePlanItem(
                        info=it.info,
                        suggested_name=new_rel.name,
                        suggested_rel_path=new_rel,
                        reason=it.reason,
                        conflict=False,
                        conflict_with=None,
                        manual=False,
                    )
                )
            else:
                applied_items.append(it)

            self.log.info(
                "renamed: %s -> %s", it.info.rel_path.as_posix(), new_rel.as_posix()
            )

        ref_res = None
        if update_refs and applied_items:
            ref_res = update_references(
                settings.repo,
                self.ctx.fs,
                renames=applied_items,
                scope_tokens=update_refs_scope,
            )
            if ref_res.updated_files:
                self.log.info("Обновлены ссылки: файлов=%s", ref_res.updated_files)
                for p in ref_res.touched_paths:
                    self.log.info(" - %s", p)
            else:
                self.log.info("Ссылки не обновлялись (совпадений не найдено).")

        result = MigrationResult(
            total_scanned=len(dirs) if scope != "changed" or limit_to_paths else 0,
            violations=len(plan),
            actionable=len(actionable),
            manual=sum(1 for it in plan if it.manual or not it.suggested_rel_path),
            conflicts=sum(1 for it in plan if it.conflict),
            applied=applied,
            skipped=skipped,
            reference_updates=ref_res,
        )

        if is_machine_output(output_fmt):
            write_payload(self._build_payload(plan, result), fmt=output_fmt)
        else:
            write_text(output_text + "\n")

        return 0
