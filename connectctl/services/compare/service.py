from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

from ...app.context import CliContext
from ...cli_helpers.routing_explain import format_routing_explain_lines
from ...comparison import ConfigComparison, compare_connector_configs
from ...exceptions import ValidationError
from ...lifecycle.guards import log_disabled_manifest_skip
from ...logging_utils import get_logger
from ...output import (
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
)
from ...rendering.factory import build_renderer
from ...rendering.prune import apply_prune_to_render_result
from ...rendering.runtime_vars import load_runtime_vars_with_sources, log_vars_used
from ...routing import ClusterRouter, format_cluster_target
from ...validation import ConfigTestRunner
from ...validation.manifest_validation import validate_manifest


@dataclass
class CompareService:
    """Compare one rendered manifest with live/file config using post-prune desired config."""

    ctx: CliContext
    logger: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        self.log = get_logger(self.logger or self.ctx.logger)

    def run(self, args) -> int:
        repo_root = self.ctx.repo_root
        settings = self.ctx.settings

        renderer = build_renderer(
            settings,
            fs=self.ctx.fs,
            routing_cli_cluster=getattr(args, "cluster", None),
            routing_suppress_tag_conflicts=bool(
                getattr(args, "suppress_tag_conflicts", False)
            ),
        )
        env_file = (repo_root / str(getattr(args, "path"))).resolve()
        runtime_vars, runtime_sources = load_runtime_vars_with_sources(args, repo_root)

        reuse_overrides = bool(getattr(args, "reuse_overrides", True))
        reuse_from_raw = getattr(args, "reuse_from", None) or []
        reuse_from = [Path(p) for p in reuse_from_raw] or None

        rr = renderer.render(
            env_file,
            runtime_vars=runtime_vars,
            runtime_var_sources=runtime_sources,
            reuse_overrides=reuse_overrides,
            reuse_from=reuse_from,
        )
        manifest = rr.manifest

        config_test_runner = ConfigTestRunner.from_settings(
            repo_root=repo_root, config_tests=settings.config_tests
        )

        router = ClusterRouter(
            settings=settings,
            env=manifest.info.env,
            cli_cluster=getattr(args, "cluster", None),
            suppress_tag_conflicts=bool(getattr(args, "suppress_tag_conflicts", False)),
            logger=lambda msg: self.log.warning("%s", msg),
        )
        decision, routing_debug = router.route_with_debug(
            connector_name=manifest.name,
            connectctl_meta=rr.connectctl,
            connectctl_sources=rr.connectctl_sources,
        )
        if bool(getattr(args, "explain_routing", False)):
            for line in format_routing_explain_lines(routing_debug):
                self.log.info("%s", line)

        if manifest.lifecycle.disabled:
            log_disabled_manifest_skip(
                manifest=manifest,
                logger=self.log,
                repo_root=repo_root,
            )
            payload = {
                "command": "compare",
                "status": "disabled",
                "comparison_mode": "post_prune",
                "routing": {
                    "cluster": {
                        "group": decision.cluster.name,
                        "env": manifest.info.env.value,
                        "urls": list(decision.cluster.urls),
                    },
                    "source": decision.source,
                    "target": format_cluster_target(decision.cluster),
                },
                "source_a": {
                    "type": "rendered_manifest",
                    "manifest": self._relpath(env_file, repo_root),
                    "connector_name": manifest.name,
                },
                "lifecycle": manifest.lifecycle.to_meta(),
            }
            fmt = resolve_output_format(args)
            if is_machine_output(fmt):
                write_payload(payload, fmt=fmt)
            else:
                write_text(
                    self._build_disabled_text_report(
                        manifest_name=manifest.name,
                        manifest_path=self._relpath(env_file, repo_root),
                        routing_target=format_cluster_target(decision.cluster),
                        routing_source=decision.source,
                        reason=manifest.lifecycle.reason or "disabled",
                        ticket=manifest.lifecycle.ticket,
                        until=manifest.lifecycle.until,
                    )
                )
            return 0

        validate_manifest(
            manifest,
            config_test_runner=config_test_runner,
            config_test_context={
                "cluster_group": decision.cluster_name,
                "tags": list(rr.connectctl.get("tags") or []),
            },
            strict_naming=bool(getattr(args, "strict_naming", True)),
            policies=bool(getattr(args, "policies", True)),
            policy_env=manifest.info.env,
            policy_layers=rr.layers,
            naming=settings.naming,
            logger=self.log,
        )

        pruned_keys: tuple[str, ...] = ()
        if decision.cluster.render_prune_config_keys:
            rr, pruned_keys = apply_prune_to_render_result(
                rr, decision.cluster.render_prune_config_keys
            )
            manifest = rr.manifest

        if bool(getattr(args, "show_vars", True)):
            log_vars_used(rr, repo_root, logger=self.log)

        target = self.ctx.connect_target(manifest.info.env, decision.cluster_name)
        self.ctx.print_cluster_banner(target)

        actual_cfg, source_b = self._load_actual_config(
            args=args,
            target=target,
            rendered_name=manifest.name,
            repo_root=repo_root,
        )

        comparison = compare_connector_configs(
            connector_name=manifest.name,
            desired=manifest.config,
            actual=actual_cfg,
        )

        payload = {
            "command": "compare",
            "comparison_mode": "post_prune",
            "routing": {
                "cluster": {
                    "group": target.cluster.name,
                    "env": target.cluster.env.value,
                    "urls": list(target.cluster.urls),
                },
                "source": decision.source,
                "target": format_cluster_target(target.cluster),
            },
            "source_a": {
                "type": "rendered_manifest",
                "manifest": self._relpath(env_file, repo_root),
                "connector_name": manifest.name,
            },
            "source_b": source_b,
            "pruned_config_keys": list(pruned_keys),
            "desired": comparison.desired_masked,
            "actual": comparison.actual_masked,
            "diff": comparison.diff_payload(),
        }

        fmt = resolve_output_format(args)
        if is_machine_output(fmt):
            write_payload(payload, fmt=fmt)
        else:
            write_text(
                self._build_text_report(
                    manifest_name=manifest.name,
                    manifest_path=self._relpath(env_file, repo_root),
                    comparison=comparison,
                    routing_target=format_cluster_target(target.cluster),
                    routing_source=decision.source,
                    pruned_keys=pruned_keys,
                    source_b=source_b,
                )
            )

        return 0

    def _load_actual_config(
        self,
        *,
        args,
        target,
        rendered_name: str,
        repo_root: Path,
    ) -> tuple[Mapping[str, Any], dict[str, Any]]:
        against = str(getattr(args, "against", "live") or "live").strip().lower()

        if against == "live":
            cfg = target.client.get_config_optional(rendered_name)
            return (cfg or {}), {
                "type": "live",
                "connector_name": rendered_name,
                "cluster": target.cluster.name,
                "found": cfg is not None,
            }

        if against == "connector":
            name = str(getattr(args, "name", "") or "").strip()
            if not name:
                raise ValidationError("--name is required for --against connector")
            cfg = target.client.get_config_optional(name)
            return (cfg or {}), {
                "type": "connector",
                "connector_name": name,
                "cluster": target.cluster.name,
                "found": cfg is not None,
            }

        if against != "file":
            raise ValidationError(
                f"Unsupported --against value: {against!r}. Expected one of: live, connector, file"
            )

        raw_path = str(getattr(args, "file", "") or "").strip()
        if not raw_path:
            raise ValidationError("--file is required for --against file")

        file_path = Path(raw_path)
        if not file_path.is_absolute():
            file_path = (repo_root / file_path).resolve()
        if not self.ctx.fs.exists(file_path) or not self.ctx.fs.is_file(file_path):
            raise ValidationError(f"Compare input file does not exist: {file_path}")

        data = self._load_mapping_file(file_path)
        if "config" in data and isinstance(data.get("config"), Mapping):
            config = dict(data["config"])
        else:
            config = dict(data)

        return config, {
            "type": "file",
            "path": str(file_path),
            "found": True,
        }

    def _load_mapping_file(self, path: Path) -> dict[str, Any]:
        text = self.ctx.fs.read_text(path, encoding="utf-8")
        suffix = path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            loaded = yaml.safe_load(text)
        else:
            loaded = json.loads(text)

        if not isinstance(loaded, Mapping):
            raise ValidationError(
                f"Compare input file must contain a JSON/YAML object: {path}"
            )
        return dict(loaded)

    def _relpath(self, path: Path, repo_root: Path) -> str:
        try:
            return str(path.relative_to(repo_root))
        except Exception:
            return str(path)

    def _build_text_report(
        self,
        *,
        manifest_name: str,
        manifest_path: str,
        comparison: ConfigComparison,
        routing_target: str,
        routing_source: str,
        pruned_keys: tuple[str, ...],
        source_b: Mapping[str, Any],
    ) -> str:
        diff_payload = comparison.diff_payload()
        lines = [
            "## bkkt compare",
            "",
            f"- Manifest: `{manifest_path}`",
            f"- Connector: `{manifest_name}`",
            f"- Routing: `{routing_target}` (source: `{routing_source}`)",
            "- Comparison mode: `post_prune`",
        ]

        source_b_type = str(source_b.get("type") or "unknown")
        if source_b_type in {"live", "connector"}:
            connector_name = str(source_b.get("connector_name") or "")
            cluster = str(source_b.get("cluster") or "")
            found = bool(source_b.get("found", False))
            state = "found" if found else "missing"
            lines.append(
                f"- Actual source: `{source_b_type}` / `{connector_name}` / cluster `{cluster}` ({state})"
            )
        else:
            lines.append(f"- Actual source: file `{source_b.get('path')}`")

        lines.append(f"- In sync: `{'yes' if comparison.in_sync else 'no'}`")
        lines.append("")
        lines.extend(self._format_keys_section("Pruned by cluster policy", pruned_keys))
        lines.append("")
        lines.extend(
            self._format_mapping_section(
                "Only in desired", diff_payload["only_in_desired"]
            )
        )
        lines.append("")
        lines.extend(
            self._format_mapping_section(
                "Only in actual", diff_payload["only_in_actual"]
            )
        )
        lines.append("")
        lines.extend(self._format_changed_section("Changed", diff_payload["changed"]))
        lines.append("")
        lines.append(
            "Result: configs are in sync."
            if comparison.in_sync
            else "Result: differences detected."
        )

        return "\n".join(lines) + "\n"

    def _build_disabled_text_report(
        self,
        *,
        manifest_name: str,
        manifest_path: str,
        routing_target: str,
        routing_source: str,
        reason: str,
        ticket: Optional[str],
        until: Optional[str],
    ) -> str:
        lines = [
            "## bkkt compare",
            "",
            f"- Manifest: `{manifest_path}`",
            f"- Connector: `{manifest_name}`",
            f"- Routing: `{routing_target}` (source: `{routing_source}`)",
            "- Status: `disabled`",
            f"- Reason: `{reason}`",
        ]
        if ticket:
            lines.append(f"- Ticket: `{ticket}`")
        if until:
            lines.append(f"- Until: `{until}`")
        lines.append("")
        lines.append(
            "Comparison skipped because this manifest is disabled via `connectctl.lifecycle`."
        )
        return "\n".join(lines) + "\n"

    def _format_keys_section(self, title: str, keys: tuple[str, ...]) -> list[str]:
        lines = [f"### {title} ({len(keys)})"]
        if not keys:
            lines.append("- (none)")
            return lines
        for key in keys:
            lines.append(f"- `{key}`")
        return lines

    def _format_mapping_section(
        self, title: str, values: Mapping[str, str]
    ) -> list[str]:
        lines = [f"### {title} ({len(values)})"]
        if not values:
            lines.append("- (none)")
            return lines
        for key, value in values.items():
            lines.append(f"- `{key}` = {value!r}")
        return lines

    def _format_changed_section(
        self, title: str, values: Mapping[str, Mapping[str, str]]
    ) -> list[str]:
        lines = [f"### {title} ({len(values)})"]
        if not values:
            lines.append("- (none)")
            return lines
        for key, pair in values.items():
            lines.append(
                f"- `{key}`: actual={pair.get('actual')!r} -> desired={pair.get('desired')!r}"
            )
        return lines
