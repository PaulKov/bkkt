from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple, cast

from ...app.context import CliContext
from ...exceptions import ConfigError
from ..name_variants import normalize_source_mode_token, split_csv, uniq_preserve

from .models import InitOptions
from .template_overrides import collect_init_template_overrides


def resolve_and_validate_connector_dir(
    *,
    domain: str,
    dataset: str,
    connector_dir: Optional[str],
    log: logging.Logger,
) -> tuple[str, str]:
    """Resolve default connector_dir and validate naming convention.

    Rules:
      connector_<domain>__<dataset>{__<optional_suffix>}

    UX:
      - if user provided connector_dir and omitted dataset (still CHANGE_ME),
        infer dataset from connector_dir when possible.
    """

    if connector_dir:
        # Friendly UX: infer dataset when the user omitted --dataset (still placeholder).
        if dataset == "CHANGE_ME":
            prefix = f"connector_{domain}__"
            if connector_dir.startswith(prefix):
                remainder = connector_dir[len(prefix) :]
                parts = remainder.split("__")
                if parts and parts[0]:
                    dataset = parts[0]
                    log.info("inferred --dataset from --connector-dir: %r", dataset)

        expected_prefix = f"connector_{domain}__{dataset}"
        if not re.match(rf"^{re.escape(expected_prefix)}(?:__.+)?$", connector_dir):
            raise ConfigError(
                "Некорректный --connector-dir. Ожидается: "
                f"connector_{domain}__{dataset}{{__<optional_suffix>}}. "
                f"Получено: {connector_dir!r}"
            )
        return connector_dir, dataset

    return f"connector_{domain}__{dataset}", dataset


def validate_mode_token(token: str) -> str:
    """Validate/normalize `--modes` tokens for `bkkt init`.

    We keep the UX simple:
    - built-ins: `cdc`, `init` (aliases: `stream` -> `cdc`, `initial` -> `init`)
    - allow custom modes (e.g. `backfill`) as long as the token is a valid dot-name segment.
    """

    return normalize_source_mode_token(token)


def _resolve_modes_and_kinds(
    *,
    connector_type: str,
    system: str,
    init_only: bool,
    modes_raw: List[str],
    kinds_raw: List[str],
    log: logging.Logger,
) -> Tuple[List[Optional[str]], List[Optional[str]]]:
    """Compute source modes and sink kinds lists."""

    # UX: if user asks for init-only scaffolding, ensure an init manifest is generated.
    if connector_type == "source" and init_only:
        has_init = any(m in {"init", "initial"} for m in modes_raw)
        if not modes_raw:
            modes_raw = ["init"]
        elif not has_init:
            log.info("--init-only подразумевает init; добавляем 'init' в --modes")
            modes_raw = ["init"] + modes_raw

    if connector_type == "source" and kinds_raw:
        raise ConfigError("--kinds поддерживается только для sink")
    if connector_type == "sink" and modes_raw:
        raise ConfigError("--modes поддерживается только для source")

    source_modes: List[Optional[str]] = [None]
    if connector_type == "source":
        if modes_raw:
            source_modes = [validate_mode_token(m) for m in uniq_preserve(modes_raw)]
        else:
            # Default: for Debezium-like systems, scaffold cdc.
            if system.lower() in {"postgres", "mysql", "mariadb"}:
                source_modes = ["cdc"]

        if init_only and not any(m == "init" for m in source_modes if m):
            raise ConfigError("--init-only требует режим init (или initial)")

    sink_kinds: List[Optional[str]] = [None]
    if connector_type == "sink":
        if kinds_raw:
            sink_kinds = cast(
                List[Optional[str]],
                uniq_preserve([k.strip() for k in kinds_raw if k.strip()]),
            )

    return source_modes, sink_kinds


def parse_init_options(*, args, ctx: CliContext, log: logging.Logger) -> InitOptions:
    repo_root = ctx.repo_root
    settings = ctx.settings

    connectors_root = settings.repo.connectors_root

    domain = str(getattr(args, "domain")).strip()
    connector_type = str(getattr(args, "connector_type")).strip()
    system = str(getattr(args, "system")).strip()

    # Dataset is used both in the default connector_dir and in default name templates.
    dataset = (getattr(args, "dataset", None) or "CHANGE_ME").strip()

    connector_dir = (getattr(args, "connector_dir", None) or "").strip() or None
    connector_dir, dataset = resolve_and_validate_connector_dir(
        domain=domain,
        dataset=dataset,
        connector_dir=connector_dir,
        log=log,
    )

    target_dir: Path = (
        connectors_root / domain / connector_type / system / connector_dir
    )

    envs = list(getattr(args, "env", None) or [])
    if not envs:
        raise ConfigError("--env обязателен (dev/stage/prod)")

    modes_raw = [m.strip().lower() for m in split_csv(getattr(args, "modes", None))]
    kinds_raw = [k.strip().lower() for k in split_csv(getattr(args, "kinds", None))]

    init_only = bool(getattr(args, "init_only", False))

    modes_explicit = bool(modes_raw) or init_only
    kinds_explicit = bool(kinds_raw)

    modes, kinds = _resolve_modes_and_kinds(
        connector_type=connector_type,
        system=system,
        init_only=init_only,
        modes_raw=modes_raw,
        kinds_raw=kinds_raw,
        log=log,
    )

    layer = str(getattr(args, "layer", "raw"))
    index = int(getattr(args, "index", 0))

    explicit_name = getattr(args, "name", None)
    name_template = getattr(args, "name_template", None)

    create_all = bool(getattr(args, "create_all", True))
    force = bool(getattr(args, "force", False))
    dry_run = bool(getattr(args, "dry_run", False))

    templates_root_name = (
        os.environ.get("BKKT_INIT_TEMPLATES_ROOT") or "__init_templates"
    ).strip() or "__init_templates"
    templates_root = repo_root / templates_root_name
    template_overrides = collect_init_template_overrides(args)
    return InitOptions(
        repo_root=repo_root,
        target_dir=target_dir,
        fs=ctx.fs,
        templates_root=templates_root,
        template_overrides=template_overrides,
        domain=domain,
        connector_type=connector_type,
        system=system,
        dataset=dataset,
        connector_dir=connector_dir,
        envs=envs,
        layer=layer,
        index=index,
        modes=modes,
        kinds=kinds,
        modes_explicit=modes_explicit,
        kinds_explicit=kinds_explicit,
        explicit_name=str(explicit_name) if explicit_name is not None else None,
        name_template=str(name_template) if name_template is not None else None,
        create_all=create_all,
        init_only=init_only,
        force=force,
        dry_run=dry_run,
    )
