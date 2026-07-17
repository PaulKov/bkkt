from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List, Mapping, Sequence

from ...comparison import compare_connector_configs
from ...diffing import summarize_diff
from ...lifecycle.guards import log_disabled_manifest_skip
from ...ports import ConnectApi
from ...repo import ConnectorRepo
from ...rendering.prune import apply_prune_to_render_result
from ...validation import ConfigTestRunner

from ...validation.manifest_validation import validate_manifest

from .models import DriftCollected, DriftOptions
from .override_sources import (
    count_override_sources_for_drift_keys,
    last_config_key_sources,
)


def collect_drift(
    *,
    policy_env,
    env_files: Sequence[Path],
    repo_root: Path,
    repo: ConnectorRepo,
    renderer,
    runtime_vars: Mapping[str, object],
    connect: ConnectApi,
    config_test_runner: ConfigTestRunner,
    strict_naming: bool,
    policies: bool,
    naming,
    options: DriftOptions,
    cluster_group: str,
    prune_config_keys: Sequence[str],
    logger,
) -> DriftCollected:
    """Собрать статистику drift для списка env-манифестов."""

    ok_count = 0
    disabled_skipped = 0
    drift_count = 0
    missing_count = 0

    drift_key_counter: Counter[str] = Counter()
    drift_override_source_counter: Counter[str] = Counter()

    group_stats_dt: DefaultDict[str, Dict[str, int]] = defaultdict(
        lambda: {"total": 0, "ok": 0, "drift": 0, "missing": 0}
    )
    group_stats_dts: DefaultDict[str, Dict[str, int]] = defaultdict(
        lambda: {"total": 0, "ok": 0, "drift": 0, "missing": 0}
    )

    detailed: List[Dict[str, object]] = []

    for pth in env_files:
        rr = renderer.render(pth, runtime_vars=runtime_vars)
        manifest = rr.manifest

        if manifest.lifecycle.disabled:
            log_disabled_manifest_skip(
                manifest=manifest,
                logger=logger,
                repo_root=repo_root,
            )
            info = manifest.info
            rel = (
                str(pth.relative_to(repo_root))
                if pth.is_absolute() and repo_root in pth.parents
                else str(pth)
            )
            detailed.append(
                {
                    "name": manifest.name,
                    "status": "disabled",
                    "domain": info.domain,
                    "type": info.connector_type.value,
                    "system": info.system,
                    "manifest_rel": rel,
                    "reason": manifest.lifecycle.reason,
                    "ticket": manifest.lifecycle.ticket,
                    "until": manifest.lifecycle.until,
                }
            )
            disabled_skipped += 1
            continue

        validate_manifest(
            manifest,
            config_test_runner=config_test_runner,
            config_test_context={
                "cluster_group": cluster_group,
                "tags": list(rr.connectctl.get("tags") or []),
            },
            strict_naming=strict_naming,
            policies=policies,
            policy_env=policy_env,
            policy_layers=rr.layers,
            naming=naming,
            logger=logger,
        )

        pruned_keys: tuple[str, ...] = ()
        if prune_config_keys:
            rr, pruned_keys = apply_prune_to_render_result(rr, prune_config_keys)
            manifest = rr.manifest

        info = manifest.info
        domain = info.domain
        ctype = info.connector_type.value
        system = info.system

        group_key_dt = f"{domain} / {ctype}"
        group_key_dts = f"{domain} / {ctype} / {system}"
        group_stats_dt[group_key_dt]["total"] += 1
        group_stats_dts[group_key_dts]["total"] += 1

        rel = (
            str(pth.relative_to(repo_root))
            if pth.is_absolute() and repo_root in pth.parents
            else str(pth)
        )
        live_cfg = connect.get_config_optional(manifest.name)
        if live_cfg is None:
            missing_count += 1
            group_stats_dt[group_key_dt]["missing"] += 1
            group_stats_dts[group_key_dts]["missing"] += 1
            detailed.append(
                {
                    "name": manifest.name,
                    "status": "missing",
                    "domain": domain,
                    "type": ctype,
                    "system": system,
                    "manifest_rel": rel,
                }
            )
            continue

        comparison = compare_connector_configs(
            connector_name=manifest.name,
            desired=manifest.config,
            actual=live_cfg,
        )

        if comparison.in_sync:
            ok_count += 1
            group_stats_dt[group_key_dt]["ok"] += 1
            group_stats_dts[group_key_dts]["ok"] += 1
            continue

        drift_count += 1
        group_stats_dt[group_key_dt]["drift"] += 1
        group_stats_dts[group_key_dts]["drift"] += 1

        diff_keys = list(comparison.changed_keys)
        for k in diff_keys:
            drift_key_counter[k] += 1

        # Count override sources for drifted keys (exclude base + env file).
        base_file = repo.find_base_file_for(pth)
        key_sources = last_config_key_sources(rr.layers)
        count_override_sources_for_drift_keys(
            diff_keys=diff_keys,
            key_sources=key_sources,
            repo_root=repo_root,
            env_file=pth,
            base_file=base_file,
            counter=drift_override_source_counter,
        )

        entry: Dict[str, object] = {
            "name": manifest.name,
            "status": "drift",
            "domain": domain,
            "type": ctype,
            "system": system,
            "manifest_rel": rel,
            "diff_keys": diff_keys,
            "pruned_config_keys": list(pruned_keys),
        }

        if options.include_diffs:
            diff_txt = comparison.unified_diff
            diff_txt, trimmed = summarize_diff(diff_txt, max_lines=options.max_lines)
            entry["diff"] = diff_txt
            entry["diff_trimmed"] = trimmed

        detailed.append(entry)

    return DriftCollected(
        manifests_checked=len(env_files),
        ok_count=ok_count,
        disabled_skipped=disabled_skipped,
        drift_count=drift_count,
        missing_count=missing_count,
        group_stats_dt=dict(group_stats_dt),
        group_stats_dts=dict(group_stats_dts),
        drift_key_counter=drift_key_counter,
        drift_override_source_counter=drift_override_source_counter,
        detailed=detailed,
    )
