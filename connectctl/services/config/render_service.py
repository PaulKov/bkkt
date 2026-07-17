from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Optional, Set

from ...app.context import CliContext
from ...cli_helpers.default_scope_ux import (
    confirm_broad_scope,
    effective_value,
    log_effective_values,
)
from ...cli_helpers.explicit_args import was_explicit
from ...exceptions import ConfigError
from ...logging_utils import get_logger
from ...models import Environment
from ...output import (
    OutputFormat,
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
    dumps_yaml,
)
from ...settings_clusters_inheritance import ClusterGroupEnvResolver
from ...utils.masking import mask_secrets_in_obj

from .raw_clusters import parse_raw_cluster_groups
from .raw_loader import load_raw_config
from .selection import (
    parse_cluster_group_filter,
    parse_env_filter,
    render_cluster_group_filter,
    render_env_filter,
    select_cluster_groups,
    select_envs,
)


class ConfigRenderService:
    """Сервис `bkkt config render`.

    Цель: вывести финальный connectctl.yaml после:
    - expand env vars (${VAR:-default})
    - разрешения from_cluster_group_env(...)

    По умолчанию секреты маскируются (***).
    """

    def __init__(self, *, ctx: CliContext, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)

    def run(self, args: argparse.Namespace) -> int:
        fmt = resolve_output_format(args, default=OutputFormat.yaml)

        # Filters
        group_filter = parse_cluster_group_filter(getattr(args, "cluster_group", None))
        env_filter = parse_env_filter(getattr(args, "env", None))

        show_secrets = bool(getattr(args, "show_secrets", False))

        log_effective_values(
            self.log,
            command="config render",
            values=(
                effective_value(
                    args,
                    "cluster_group",
                    render_cluster_group_filter(group_filter),
                    name="cluster_group",
                ),
                effective_value(
                    args,
                    "env",
                    render_env_filter(env_filter),
                ),
                effective_value(args, "output", fmt.value),
                effective_value(args, "show_secrets", show_secrets),
            ),
        )

        if _requires_broad_render_confirmation(
            args,
            fmt=fmt,
            group_filter=group_filter,
            env_filter=env_filter,
        ):
            if not confirm_broad_scope(
                args,
                prompt="Продолжить широкий config render для всех cluster groups и env?",
                logger=self.log,
            ):
                return 1

        raw = load_raw_config(self.ctx.config_path, fs=self.ctx.fs)
        clusters_raw = raw.data.get("clusters", {})

        parsed_raw = parse_raw_cluster_groups(clusters_raw)
        resolver = ClusterGroupEnvResolver(parsed_raw.groups)

        selected_groups = select_cluster_groups(
            parsed_raw.groups.keys(), include=group_filter
        )

        clusters_out: Dict[str, Any]
        if parsed_raw.legacy:
            # Legacy config: clusters: {dev: {...}, prod: {...}}.
            # group name is always "default".
            if selected_groups and selected_groups != ["default"]:
                raise ConfigError(
                    "Legacy clusters format does not support multiple cluster groups. "
                    "Use --cluster-group only with multi-cluster config."
                )

            envs = select_envs(parsed_raw.groups["default"].keys(), include=env_filter)
            clusters_out = {
                env.value: dict(resolver.resolve_env_mapping("default", env=env))
                for env in envs
            }
        else:
            clusters_out = {}
            for group in selected_groups:
                envs = select_envs(parsed_raw.groups[group].keys(), include=env_filter)
                clusters_out[group] = {
                    env.value: dict(resolver.resolve_env_mapping(group, env=env))
                    for env in envs
                }

        out_cfg: Dict[str, Any] = dict(raw.data)
        out_cfg["clusters"] = clusters_out

        if not show_secrets:
            out_cfg = mask_secrets_in_obj(out_cfg)

        out_text: Optional[str] = None
        if not is_machine_output(fmt):
            # Для человека удобнее YAML — даже если пользователь выбрал "text".
            out_text = dumps_yaml(out_cfg, sort_keys=False)
            write_text(out_text)
        else:
            write_payload(out_cfg, fmt=fmt)

        out_path = getattr(args, "output_file", None)
        if out_path:
            # Пишем в файл в том же формате, что и stdout.
            if out_text is None:
                if fmt == OutputFormat.json:
                    # reuse write_payload output format via dumps_yaml is not possible; use write_payload but capture? easier: dumps_yaml/dumps_json
                    from ...output import dumps_json

                    out_text = dumps_json(out_cfg)
                else:
                    out_text = dumps_yaml(out_cfg, sort_keys=False)
            self.ctx.fs.write_text(Path(str(out_path)), out_text, encoding="utf-8")

        return 0


def _requires_broad_render_confirmation(
    args: argparse.Namespace,
    *,
    fmt: OutputFormat,
    group_filter: Optional[Set[str]],
    env_filter: Optional[Set[Environment]],
) -> bool:
    if is_machine_output(fmt):
        return False
    return (
        group_filter is None
        and env_filter is None
        and not was_explicit(args, "cluster_group")
        and not was_explicit(args, "env")
    )
