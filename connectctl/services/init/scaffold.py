from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Set

from ...exceptions import ConfigError

from .models import InitOptions
from .naming import build_connector_name
from .template_engine import (
    InitFileTemplateResult,
    build_all_json,
    build_env_json,
    build_mode_all_json,
    build_mode_env_json,
    build_type_all_json,
    build_type_env_json,
)
from .writer import ensure_dir, relpath, write_json


def _log_template_result(
    res: InitFileTemplateResult, *, repo_root: Path, log: logging.Logger
) -> None:
    """Pretty logging for init-template resolution."""
    log.info("Init template: %s", relpath(repo_root, res.out_path))

    # Template layers
    if res.template_layers:
        log.info("  template layers (low -> high):")
        for layer in res.template_layers:
            log.info("   - %s", layer)

    # Overrides (env/CLI)
    if res.override_layers:
        log.info("  value overrides (low -> high):")
        for ov in res.override_layers:
            log.info("   - %s", ov)

    log.info(
        "  result counters: vars=%s, config=%s", res.count_vars(), res.count_config()
    )


def scaffold_repo_files(*, opts: InitOptions, log: logging.Logger) -> List[Path]:
    """Create directories and manifests for `bkkt init`.

    Returns a list of written (or planned, in dry-run) paths.

    DIP:
    - запись/проверка наличия файлов идёт через FileSystem порт (opts.fs).
    """

    repo_root = opts.repo_root
    target_dir = opts.target_dir
    fs = opts.fs

    created: List[Path] = []

    # Summary (important for UX, esp. with --dry-run)
    log.info(
        "Init scaffold: type=%s system=%s domain=%s dataset=%s connector_dir=%s",
        opts.connector_type,
        opts.system,
        opts.domain,
        opts.dataset,
        opts.connector_dir,
    )
    log.info("Target dir: %s", relpath(repo_root, target_dir))
    modes_s = ",".join([str(m) if m is not None else "none" for m in opts.modes])
    kinds_s = ",".join([str(k) if k is not None else "none" for k in opts.kinds])
    log.info(
        "Variants: envs=%s modes=%s kinds=%s (modes_explicit=%s kinds_explicit=%s)",
        ",".join(opts.envs),
        modes_s,
        kinds_s,
        opts.modes_explicit,
        opts.kinds_explicit,
    )

    ensure_dir(target_dir, fs=fs, repo_root=repo_root, dry_run=opts.dry_run, log=log)

    # Base layer templates: all.json + <env>.json (if enabled).
    if opts.create_all:
        all_res = build_all_json(opts, log=log)
        _log_template_result(all_res, repo_root=repo_root, log=log)

        if fs.exists(all_res.out_path) and not opts.force:
            log.info("skip (exists): %s", relpath(repo_root, all_res.out_path))
        else:
            write_json(
                all_res.out_path,
                all_res.data,
                fs=fs,
                repo_root=repo_root,
                dry_run=opts.dry_run,
                created=created,
                log=log,
            )

        for env in opts.envs:
            env_res = build_env_json(opts, env, log=log)
            _log_template_result(env_res, repo_root=repo_root, log=log)

            if fs.exists(env_res.out_path) and not opts.force:
                log.info("skip (exists): %s", relpath(repo_root, env_res.out_path))
            else:
                write_json(
                    env_res.out_path,
                    env_res.data,
                    fs=fs,
                    repo_root=repo_root,
                    dry_run=opts.dry_run,
                    created=created,
                    log=log,
                )

    # Optional (extended): scaffold mode overlays for source.
    #
    # Behaviour is intentionally "explicit":
    # - by default (`bkkt init ...` without --modes) we do NOT create modes/* files
    #   to avoid extra clutter.
    # - if user requested modes explicitly (or via --init-only), we scaffold them.
    # - special case: even if create_all is disabled, --init-only still produces
    #   modes/init/all.json (as before).

    modes_to_scaffold: List[str] = []
    scaffold_mode_env = False
    if opts.connector_type == "source" and opts.modes_explicit and opts.create_all:
        modes_to_scaffold = [m for m in opts.modes if m]
        scaffold_mode_env = True
    elif opts.init_only:
        if opts.connector_type != "source":
            raise ConfigError("--init-only поддерживается только для source")
        modes_to_scaffold = ["init"]

    for mode in list(dict.fromkeys(modes_to_scaffold)):
        mode_dir = target_dir / "modes" / mode
        ensure_dir(mode_dir, fs=fs, repo_root=repo_root, dry_run=opts.dry_run, log=log)

        mode_all_res = build_mode_all_json(opts, mode, log=log)
        _log_template_result(mode_all_res, repo_root=repo_root, log=log)

        if fs.exists(mode_all_res.out_path) and not opts.force:
            log.info("skip (exists): %s", relpath(repo_root, mode_all_res.out_path))
        else:
            write_json(
                mode_all_res.out_path,
                mode_all_res.data,
                fs=fs,
                repo_root=repo_root,
                dry_run=opts.dry_run,
                created=created,
                log=log,
            )

        if scaffold_mode_env:
            for env in opts.envs:
                mode_env_res = build_mode_env_json(opts, mode, env, log=log)
                _log_template_result(mode_env_res, repo_root=repo_root, log=log)
                if fs.exists(mode_env_res.out_path) and not opts.force:
                    log.info(
                        "skip (exists): %s", relpath(repo_root, mode_env_res.out_path)
                    )
                else:
                    write_json(
                        mode_env_res.out_path,
                        mode_env_res.data,
                        fs=fs,
                        repo_root=repo_root,
                        dry_run=opts.dry_run,
                        created=created,
                        log=log,
                    )

    # Optional (extended): scaffold sink type (kind) overlays.
    if opts.connector_type == "sink" and opts.kinds_explicit and opts.create_all:
        for kind in list(dict.fromkeys([k for k in opts.kinds if k])):
            kind_dir = target_dir / "types" / kind
            ensure_dir(
                kind_dir, fs=fs, repo_root=repo_root, dry_run=opts.dry_run, log=log
            )

            type_all_res = build_type_all_json(opts, kind, log=log)
            _log_template_result(type_all_res, repo_root=repo_root, log=log)
            if fs.exists(type_all_res.out_path) and not opts.force:
                log.info("skip (exists): %s", relpath(repo_root, type_all_res.out_path))
            else:
                write_json(
                    type_all_res.out_path,
                    type_all_res.data,
                    fs=fs,
                    repo_root=repo_root,
                    dry_run=opts.dry_run,
                    created=created,
                    log=log,
                )

            for env in opts.envs:
                type_env_res = build_type_env_json(opts, kind, env, log=log)
                _log_template_result(type_env_res, repo_root=repo_root, log=log)
                if fs.exists(type_env_res.out_path) and not opts.force:
                    log.info(
                        "skip (exists): %s", relpath(repo_root, type_env_res.out_path)
                    )
                else:
                    write_json(
                        type_env_res.out_path,
                        type_env_res.data,
                        fs=fs,
                        repo_root=repo_root,
                        dry_run=opts.dry_run,
                        created=created,
                        log=log,
                    )

    planned_paths: Set[Path] = set()
    planned_names: List[str] = []

    # Generate concrete connector manifests.
    # IMPORTANT: `modes`/`kinds` may contain `None` (implicit default).
    # Filtering-out falsy values breaks init for:
    # - source connectors (kinds=[None])
    # - sink connectors (modes=[None])
    for env in opts.envs:
        for mode_opt in opts.modes:
            for kind_opt in opts.kinds:
                name = build_connector_name(
                    env=str(env),
                    domain=opts.domain,
                    connector_type=opts.connector_type,
                    system=opts.system,
                    connector_dir=opts.connector_dir,
                    dataset=opts.dataset,
                    layer=opts.layer,
                    index=opts.index,
                    mode=mode_opt,
                    kind=kind_opt,
                    explicit_name=opts.explicit_name,
                    name_template=opts.name_template,
                )

                planned_names.append(name)

                manifest_path = target_dir / f"{name}.json"
                if manifest_path in planned_paths:
                    raise ConfigError(
                        "init генерирует дублирующий путь манифеста: "
                        f"{relpath(repo_root, manifest_path)}. "
                        "Проверьте --modes/--kinds/--name-template."
                    )
                planned_paths.add(manifest_path)

                if fs.exists(manifest_path) and not opts.force:
                    log.info("skip (exists): %s", relpath(repo_root, manifest_path))
                    continue

                write_json(
                    manifest_path,
                    {"name": name},
                    fs=fs,
                    repo_root=repo_root,
                    dry_run=opts.dry_run,
                    created=created,
                    log=log,
                )

    # Planned connectors summary (limit output)
    uniq_names = list(dict.fromkeys(planned_names))
    preview = uniq_names[:10]
    tail = len(uniq_names) - len(preview)
    if tail > 0:
        log.info(
            "Planned connectors (%d): %s ... +%d",
            len(uniq_names),
            ", ".join(preview),
            tail,
        )
    else:
        log.info("Planned connectors (%d): %s", len(uniq_names), ", ".join(preview))

    if created:
        log.info("Created:")
        for p in created:
            log.info("- %s", relpath(repo_root, p))

    return created
