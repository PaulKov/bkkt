from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

from ...logging_utils import get_logger
from ...output import (
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
)
from ...ports import FileSystem
from ...settings_models import Settings


@dataclass(frozen=True)
class RepoDoctorCheck:
    id: str
    level: str  # ok|warn|error|info
    message: str
    hint: str = ""


@dataclass(frozen=True)
class RepoDoctorResult:
    checks: Sequence[RepoDoctorCheck]

    def counts(self) -> Dict[str, int]:
        out = {"ok": 0, "info": 0, "warn": 0, "error": 0}
        for c in self.checks:
            out[c.level] = out.get(c.level, 0) + 1
        return out

    def to_payload(self) -> Dict[str, Any]:
        return {
            "command": "repo doctor",
            "summary": self.counts(),
            "checks": [
                {
                    "id": c.id,
                    "level": c.level,
                    "message": c.message,
                    "hint": c.hint,
                }
                for c in self.checks
            ],
            "markdown": self.to_markdown(),
        }

    def to_markdown(self) -> str:
        marks = {
            "ok": "✅",
            "info": "ℹ️",
            "warn": "⚠️",
            "error": "❌",
        }

        lines: List[str] = []
        lines.append("## Repo doctor\n\n")
        counts = self.counts()
        lines.append(
            f"> Summary: ✅ {counts.get('ok', 0)} | ℹ️ {counts.get('info', 0)} | ⚠️ {counts.get('warn', 0)} | ❌ {counts.get('error', 0)}\n\n"
        )

        for c in self.checks:
            mark = marks.get(c.level, "•")
            lines.append(f"- {mark} **{c.id}**: {c.message}\n")
            if c.hint:
                lines.append(f"  - hint: {c.hint}\n")

        lines.append("\n")
        return "".join(lines)


class RepoDoctorService:
    """Repository structure checks.

    Command: `bkkt repo doctor`

    Goal:
      - help users of the manifests repo quickly validate that the repo is ready
        for BKKT (GitOps) workflows.
      - detect common mistakes (missing __global/__init_templates, not ignored dirs, etc.)
    """

    def __init__(self, *, ctx, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or getattr(ctx, "logger", None))

    def run(self, args) -> int:
        repo_root = Path(getattr(self.ctx, "repo_root", ".")).resolve()
        fs: FileSystem = getattr(self.ctx, "fs")
        settings: Settings = getattr(self.ctx, "settings")

        templates_root_name = (
            os.environ.get("BKKT_INIT_TEMPLATES_ROOT") or "__init_templates"
        ).strip() or "__init_templates"

        res = self._build_result(
            repo_root=repo_root,
            fs=fs,
            settings=settings,
            templates_root_name=templates_root_name,
        )

        fmt = resolve_output_format(args)
        if is_machine_output(fmt):
            write_payload(res.to_payload(), fmt=fmt)
        else:
            write_text(res.to_markdown())

        strict = bool(getattr(args, "strict", False))
        counts = res.counts()
        if counts.get("error", 0) > 0:
            return 2
        if strict and counts.get("warn", 0) > 0:
            return 2
        return 0

    def _build_result(
        self,
        *,
        repo_root: Path,
        fs: FileSystem,
        settings: Settings,
        templates_root_name: str,
    ) -> RepoDoctorResult:
        checks: List[RepoDoctorCheck] = []

        # --- config
        cfg_path = getattr(self.ctx, "config_path", None)
        if cfg_path is not None:
            checks.append(
                RepoDoctorCheck(
                    id="config", level="ok", message=f"config loaded: {cfg_path}"
                )
            )
        else:
            checks.append(
                RepoDoctorCheck(
                    id="config",
                    level="warn",
                    message="config_path is not available in ctx",
                )
            )

        # --- connectors_root
        cr = settings.repo.connectors_root
        if fs.is_dir(cr):
            checks.append(
                RepoDoctorCheck(
                    id="connectors_root", level="ok", message=f"connectors_root: {cr}"
                )
            )
        else:
            checks.append(
                RepoDoctorCheck(
                    id="connectors_root",
                    level="error",
                    message=f"connectors_root does not exist or not a directory: {cr}",
                    hint="Проверьте connectctl.yaml: connectors_root должен указывать на директорию с доменами.",
                )
            )

        # --- required helper dirs
        global_dir = repo_root / "__global"
        if fs.is_dir(global_dir):
            checks.append(
                RepoDoctorCheck(id="__global", level="ok", message="__global/ exists")
            )
        else:
            checks.append(
                RepoDoctorCheck(
                    id="__global",
                    level="warn",
                    message="__global/ is missing",
                    hint="Сгенерируйте дефолты: bkkt repo bootstrap (или bkkt repo bootstrap --only global)",
                )
            )

        templates_dir = repo_root / templates_root_name
        if fs.is_dir(templates_dir):
            checks.append(
                RepoDoctorCheck(
                    id="init_templates",
                    level="ok",
                    message=f"init templates dir exists: {templates_root_name}/",
                )
            )
        else:
            checks.append(
                RepoDoctorCheck(
                    id="init_templates",
                    level="warn",
                    message=f"init templates dir is missing: {templates_root_name}/",
                    hint="Сгенерируйте дефолты: bkkt repo bootstrap --only init-templates",
                )
            )

        schemas_dir = repo_root / "schemas"
        if fs.is_dir(schemas_dir):
            checks.append(
                RepoDoctorCheck(id="schemas", level="ok", message="schemas/ exists")
            )
        else:
            checks.append(
                RepoDoctorCheck(
                    id="schemas",
                    level="info",
                    message="schemas/ is missing (optional)",
                    hint="validate работает и без schemas/ (есть fallback в пакете), но schemas полезны для IDE. Можно создать: bkkt repo bootstrap --only schemas",
                )
            )

        # --- ignore dirs sanity
        ignore = set(settings.repo.ignore_dirs)
        for d in ["__global", templates_root_name, "schemas"]:
            abs_dir = repo_root / d
            if fs.is_dir(abs_dir) and d not in ignore:
                checks.append(
                    RepoDoctorCheck(
                        id="ignore_dirs",
                        level="warn",
                        message=f"directory '{d}/' exists but is NOT in repo.ignore_dirs",
                        hint=(
                            "Добавьте в connectctl.yaml: ignore_dirs: ['%s', ...] чтобы BKKT не пытался парсить эти JSON как манифесты коннекторов."
                            % d
                        ),
                    )
                )

        # --- cluster config summary
        checks.append(
            RepoDoctorCheck(
                id="clusters",
                level="ok",
                message=f"default_cluster='{settings.default_cluster}', cluster_groups={sorted(settings.cluster_groups.keys())}",
            )
        )

        # --- tags + naming info
        tag_n = len(settings.tags.definitions or {})
        checks.append(
            RepoDoctorCheck(
                id="tags",
                level="info",
                message=f"tags: definitions={tag_n}, hard_conflict_params={list(settings.tags.hard_conflict_params)}",
            )
        )
        checks.append(
            RepoDoctorCheck(
                id="naming",
                level="info",
                message=f"naming: enabled={settings.naming.enabled}, strict={settings.naming.strict}, rules={len(settings.naming.rules)}",
            )
        )

        return RepoDoctorResult(checks=checks)
