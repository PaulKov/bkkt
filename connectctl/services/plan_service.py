from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Optional

from ..app.context import CliContext
from ..git_changes import expand_renames
from ..git import diff_name_status, get_head_sha, guess_base_sha
from ..logging_utils import get_logger
from ..models import Environment
from ..output import OutputFormat, resolve_output_format, write_payload, write_text
from ..planning import Planner
from ..repo import ConnectorRepo, LayerResolver


@dataclass
class PlanService:
    """Сервис `connectctl plan`.

    Вычисляет, какие manifests нужно применить/удалить по git diff.
    Никаких side effects (только план).
    """

    ctx: CliContext
    logger: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        self.log = get_logger(self.logger or self.ctx.logger)

    def run(self, args) -> int:
        repo_root = self.ctx.repo_root
        settings = self.ctx.settings

        env = Environment.from_str(getattr(args, "env"))

        base = getattr(args, "base", None) or guess_base_sha()
        head = getattr(args, "head", None) or get_head_sha()

        changes = diff_name_status(base, head, repo_root=repo_root)
        changes = expand_renames(changes)

        repo = ConnectorRepo(settings.repo, fs=self.ctx.fs)
        planner = Planner(
            repo=repo, layer_resolver=LayerResolver(settings.repo, fs=self.ctx.fs)
        )

        plan = planner.plan(env=env, changes=changes, repo_root=repo_root)

        payload = {
            "command": "plan",
            "env": env.value,
            "base": base,
            "head": head,
            "apply": [p.relative_to(repo_root).as_posix() for p in plan.to_apply],
            "delete": [str(p) for p in plan.to_delete_paths],
            "counts": {
                "apply": len(plan.to_apply),
                "delete": len(plan.to_delete_paths),
            },
        }

        fmt = resolve_output_format(args)
        if fmt in (OutputFormat.json, OutputFormat.yaml):
            write_payload(payload, fmt=fmt)
            return 0

        # text: человеко-читаемый план в stdout
        md_lines = []
        md_lines.append("# BKKT: План изменений (plan)\n")
        md_lines.append(f"- env: **{env.value}**")
        md_lines.append(f"- diff: `{base}..{head}`\n")
        md_lines.append(f"## Apply ({len(plan.to_apply)})")
        if plan.to_apply:
            for p in plan.to_apply:
                try:
                    rel = p.relative_to(repo_root)
                except ValueError:
                    rel = p
                md_lines.append(f"- `{rel.as_posix()}`")
        else:
            md_lines.append("- (пусто)")

        md_lines.append("")
        md_lines.append(f"## Delete ({len(plan.to_delete_paths)})")
        if plan.to_delete_paths:
            for p in plan.to_delete_paths:
                md_lines.append(f"- `{p}`")
        else:
            md_lines.append("- (пусто)")
        md_lines.append("")

        write_text("\n".join(md_lines) + "\n")
        return 0
