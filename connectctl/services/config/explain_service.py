from __future__ import annotations

import argparse
from typing import Any, Dict, List, Mapping, Optional

from ...app.context import CliContext
from ...exceptions import ConfigError
from ...logging_utils import get_logger
from ...models import KafkaConfig
from ...output import (
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
)
from ...settings_clusters_env import parse_cluster_env_cfg
from ...settings_clusters_inheritance import ClusterGroupEnvResolver
from ...settings_clusters_inheritance_parse import parse_from_cluster_group_env_call

from .models import ConfigExplainResult, InheritanceCall
from .raw_clusters import parse_raw_cluster_groups
from .raw_loader import load_raw_config


def _mask_kafka(cfg: Optional[KafkaConfig]) -> Optional[Dict[str, Any]]:
    if cfg is None:
        return None
    d: Dict[str, Any] = {
        "bootstrap_servers": list(cfg.bootstrap_servers),
        "security_protocol": cfg.security_protocol,
        "sasl_mechanism": cfg.sasl_mechanism,
        "sasl_plain_username": cfg.sasl_plain_username,
        "sasl_plain_password": "***" if cfg.sasl_plain_password else None,
        "ssl_cafile": cfg.ssl_cafile,
        "iam_region": cfg.iam_region,
        "aws_profile": cfg.aws_profile,
    }
    # Remove nulls for readability
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


def _collect_calls(obj: Any, *, base_path: str) -> List[InheritanceCall]:
    calls: List[InheritanceCall] = []

    def walk(x: Any, path: str) -> None:
        if isinstance(x, str):
            call = parse_from_cluster_group_env_call(x)
            if call is not None:
                ref_group, selector = call
                calls.append(
                    InheritanceCall(
                        path=path,
                        raw=x,
                        ref_group=ref_group,
                        selector=selector,
                    )
                )
            return
        if isinstance(x, Mapping):
            for k, v in x.items():
                walk(v, f"{path}.{k}")
            return
        if isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]")
            return

    walk(obj, base_path)
    return calls


def _to_yaml_like(obj: Mapping[str, Any], *, indent: int = 0) -> str:
    """Простой YAML-like pretty print для mapping (без зависимости от yaml.safe_dump)."""
    lines: List[str] = []
    pad = " " * indent
    for k, v in obj.items():
        if isinstance(v, Mapping):
            lines.append(f"{pad}{k}:")
            lines.append(_to_yaml_like(v, indent=indent + 2))
        elif isinstance(v, list):
            if not v:
                lines.append(f"{pad}{k}: []")
            else:
                lines.append(f"{pad}{k}:")
                for item in v:
                    lines.append(f"{pad}  - {item}")
        else:
            lines.append(f"{pad}{k}: {v}")
    return "\n".join(lines)


def _build_markdown(res: ConfigExplainResult) -> str:
    lines: List[str] = []
    lines.append("# BKKT: Explain clusters config\n")
    lines.append(f"- Файл: `{res.config_path}`")
    lines.append(f"- cluster_group: **{res.cluster_group}**")
    lines.append(f"- env: **{res.env.value}**\n")
    lines.append("## Connect endpoints\n")
    for url in res.connect_urls:
        lines.append(f"- {url}")
    lines.append("")
    if res.kafka:
        lines.append("## Kafka (опционально)\n")
        lines.append("```yaml")
        lines.append(_to_yaml_like(res.kafka))
        lines.append("```\n")
    if res.inheritance_calls:
        lines.append("## from_cluster_group_env(...) в исходном YAML\n")
        for c in res.inheritance_calls:
            lines.append(
                f"- `{c.path}` ← `{c.raw}` (group={c.ref_group}, selector={c.selector})"
            )
        lines.append("")
    lines.append("## Resolved env mapping\n")
    lines.append("```yaml")
    lines.append(_to_yaml_like(res.resolved_env_cfg))
    lines.append("```\n")
    return "\n".join(lines)


class ConfigExplainService:
    def __init__(self, *, ctx: CliContext, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)

    def run(self, args: argparse.Namespace) -> int:
        group = str(
            getattr(args, "cluster_group", "") or self.ctx.settings.default_cluster
        ).strip()
        env = self.ctx.env(getattr(args, "env"))
        fmt = resolve_output_format(args)

        raw = load_raw_config(self.ctx.config_path, fs=self.ctx.fs)
        clusters_raw = raw.data.get("clusters", {})
        parsed = parse_raw_cluster_groups(clusters_raw)

        if group not in parsed.groups:
            raise ConfigError(
                f"Unknown cluster group: {group}. Available: {sorted(parsed.groups.keys())}"
            )

        if env not in parsed.groups[group]:
            raise ConfigError(f"clusters.{group} does not define env '{env.value}'")

        raw_obj = parsed.groups[group][env]
        calls = _collect_calls(raw_obj, base_path=f"clusters.{group}.{env.value}")

        resolver = ClusterGroupEnvResolver(parsed.groups)
        resolved_env_cfg = dict(resolver.resolve_env_mapping(group, env=env))

        cluster_cfg = parse_cluster_env_cfg(
            cluster_name=group, env=env, env_cfg=resolved_env_cfg
        )

        res = ConfigExplainResult(
            config_path=self.ctx.config_path,
            cluster_group=group,
            env=env,
            resolved_env_cfg=resolved_env_cfg,
            connect_urls=tuple(cluster_cfg.urls),
            kafka=_mask_kafka(cluster_cfg.kafka),
            inheritance_calls=tuple(calls),
        )

        payload = {
            "config_path": str(res.config_path),
            "cluster_group": res.cluster_group,
            "env": res.env.value,
            "connect_urls": list(res.connect_urls),
            "kafka": res.kafka,
            "inheritance_calls": [
                {
                    "path": c.path,
                    "raw": c.raw,
                    "ref_group": c.ref_group,
                    "selector": c.selector,
                }
                for c in res.inheritance_calls
            ],
            "resolved_env_cfg": res.resolved_env_cfg,
        }

        if is_machine_output(fmt):
            write_payload(payload, fmt=fmt)
        else:
            write_text(_build_markdown(res))
        return 0
