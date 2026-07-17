from __future__ import annotations

import argparse
from typing import Dict, List, Sequence, Tuple

from ...app.context import CliContext
from ...logging_utils import get_logger
from ...models import Environment
from ...output import (
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
)
from ...settings_clusters import parse_cluster_groups

from .models import ConfigValidationResult, ConfigWarning
from .raw_clusters import parse_raw_cluster_groups
from .raw_loader import load_raw_config


def _envs_order() -> Tuple[Environment, ...]:
    return (Environment.dev, Environment.stage, Environment.prod)


def _fmt_env_list(envs: Sequence[Environment]) -> str:
    return ", ".join([e.value for e in envs]) if envs else "-"


def _build_markdown(result: ConfigValidationResult) -> str:
    lines: List[str] = []
    lines.append("# BKKT: Проверка connectctl.yaml\n")
    lines.append(f"- Файл: `{result.config_path}`\n")
    lines.append(f"- default_cluster: **{result.default_cluster}**\n")
    lines.append("## Cluster groups\n")
    lines.append("| Группа | Env |")
    lines.append("|---|---|")
    for g, envs in sorted(result.cluster_groups.items()):
        lines.append(f"| `{g}` | {_fmt_env_list(envs)} |")
    lines.append("")
    if result.warnings:
        lines.append("## Предупреждения\n")
        for w in result.warnings:
            lines.append(f"- **{w.code}**: {w.message}")
        lines.append("")
    lines.append("✅ Конфиг загружается и парсится успешно.\n")
    return "\n".join(lines)


class ConfigValidateService:
    def __init__(self, *, ctx: CliContext, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)

    def run(self, args: argparse.Namespace) -> int:
        strict = bool(getattr(args, "strict", False))
        fmt = resolve_output_format(args)

        raw = load_raw_config(self.ctx.config_path, fs=self.ctx.fs)

        clusters_raw = raw.data.get("clusters", {})
        parsed_raw = parse_raw_cluster_groups(clusters_raw)

        # Validate fully by reusing the same parsing logic as Settings loader.
        # If something is wrong (cycle/missing env/invalid selector), parse_cluster_groups will raise.
        _ = parse_cluster_groups(clusters_raw)  # noqa: F841

        default_cluster = self.ctx.settings.default_cluster

        warnings: List[ConfigWarning] = []

        for group, env_map in sorted(parsed_raw.groups.items()):
            envs_present = set(env_map.keys())
            missing = [e for e in _envs_order() if e not in envs_present]
            if missing:
                warnings.append(
                    ConfigWarning(
                        code="MISSING_ENV",
                        message=f"clusters.{group} не содержит env: {', '.join([e.value for e in missing])}",
                    )
                )

        cluster_groups_envs: Dict[str, Sequence[Environment]] = {
            g: tuple(sorted(env_map.keys(), key=lambda e: e.value))
            for g, env_map in parsed_raw.groups.items()
        }

        ok = True
        if strict and warnings:
            ok = False

        result = ConfigValidationResult(
            config_path=self.ctx.config_path,
            default_cluster=default_cluster,
            cluster_groups=cluster_groups_envs,
            warnings=tuple(warnings),
            ok=ok,
        )

        payload = {
            "config_path": str(result.config_path),
            "default_cluster": result.default_cluster,
            "cluster_groups": {
                k: [e.value for e in v] for k, v in result.cluster_groups.items()
            },
            "warnings": [
                {"code": w.code, "message": w.message} for w in result.warnings
            ],
            "ok": result.ok,
        }

        if is_machine_output(fmt):
            write_payload(payload, fmt=fmt)
        else:
            write_text(_build_markdown(result))

        if not result.ok:
            return 2
        return 0
