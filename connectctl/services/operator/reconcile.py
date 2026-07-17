from __future__ import annotations

import logging
from typing import Any, Optional

from ...app.context import CliContext
from ...exceptions import ConfigError
from ...output import OutputFormat, write_payload, write_text
from ..export_service import ExportService
from .discovery import DiscoveryOptions, DiscoveryService
from .formatting import join_csv


class ReconcileService:
    """Prepare live-to-Git reconciliation using the existing export engine."""

    def __init__(self, *, ctx: CliContext, logger: Optional[logging.Logger] = None):
        self.ctx = ctx
        self.log = logger or ctx.logger

    def run(self, args: Any) -> int:
        if str(getattr(args, "source", "live")) != "live":
            raise ConfigError("reconcile currently supports --source live only")
        names = self._resolve_names(args)
        payload = {
            "source": "live",
            "env": getattr(args, "env", None),
            "cluster": getattr(args, "cluster", None)
            or self.ctx.settings.default_cluster,
            "dry_run": (not bool(getattr(args, "write", False)))
            or bool(getattr(args, "dry_run", False)),
            "write": bool(getattr(args, "write", False)),
            "names": names,
            "mr_description": render_reconcile_mr_description(names=names, args=args),
        }
        if not names:
            self._emit(payload, args=args)
            return 0

        export_args = _ExportArgs.from_reconcile(args=args, names=names)
        ExportService(ctx=self.ctx, logger=self.log).run(export_args)
        self._emit(payload, args=args)
        return 0

    def _resolve_names(self, args: Any) -> list[str]:
        explicit_names = _split_csv(getattr(args, "names", None))
        if explicit_names:
            return explicit_names
        regexp = str(getattr(args, "regexp", "") or "").strip()
        if not regexp:
            raise ConfigError("reconcile requires --names or --regexp")
        options = DiscoveryOptions.from_args(args, default_limit=None)
        discovery = DiscoveryService(ctx=self.ctx, logger=self.log).resolve(
            f"re:{regexp}", options=options, args=args
        )
        return [
            item.facts.name for item in discovery.results if item.facts.origin == "live"
        ]

    def _emit(self, payload: dict[str, Any], *, args: Any) -> None:
        output = str(getattr(args, "output", "markdown") or "markdown")
        if output == "json":
            write_payload(payload, fmt=OutputFormat.json)
            return
        if output == "yaml":
            write_payload(payload, fmt=OutputFormat.yaml)
            return
        write_text(payload["mr_description"])


class _ExportArgs:
    """Small adapter object accepted by ExportService without changing export API."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)

    @classmethod
    def from_reconcile(cls, *, args: Any, names: list[str]) -> "_ExportArgs":
        write = bool(getattr(args, "write", False))
        return cls(
            env=getattr(args, "env"),
            cluster=getattr(args, "cluster", None),
            all=False,
            type=None,
            domain=getattr(args, "domain", None),
            system=getattr(args, "system", None),
            connector_dir=getattr(args, "connector_dir", None),
            auto_index_suffix_on_collision=None,
            regexp=[],
            dry_run=not write or bool(getattr(args, "dry_run", False)),
            force=bool(getattr(args, "force", False)),
            jobs=getattr(args, "jobs", 1),
            rate_limit_per_second=getattr(args, "rate_limit_per_second", 0),
            burst=getattr(args, "burst", None),
            reuse_overrides=not bool(getattr(args, "raw", False)),
            save_diffs=True,
            reuse_from=[],
            modes=[],
            init_only=False,
            kinds=[],
            as_names=[],
            iceberg_generate_kinds=[],
            iceberg_table_id_columns=[],
            iceberg_generate_overrides=True,
            iceberg_generate_manifests=True,
            names=names,
            vars=None,
            vars_file=None,
        )


def render_reconcile_mr_description(*, names: list[str], args: Any) -> str:
    lines = [
        "# BKKT live-to-Git reconcile\n\n",
        "## Summary\n\n",
        "Export selected live Kafka Connect configs into GitOps manifests using BKKT export engine.\n\n",
        "## Scope\n\n",
        f"- env: `{getattr(args, 'env', '-')}`\n",
        f"- cluster: `{getattr(args, 'cluster', None) or 'default'}`\n",
        f"- mode: `{'write' if bool(getattr(args, 'write', False)) else 'dry-run'}`\n",
        f"- connectors: `{join_csv(names)}`\n\n",
        "## Validation\n\n",
        "- `bkkt validate --strict-naming --strict-schema`\n",
        "- `bkkt drift --env <env> --cluster <cluster>` after merge/deploy if needed\n",
    ]
    return "".join(lines)


def _split_csv(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        parts = [str(item) for item in raw]
    else:
        parts = [str(raw)]
    values: list[str] = []
    for part in parts:
        values.extend(chunk.strip() for chunk in part.split(",") if chunk.strip())
    return values


__all__ = ["ReconcileService", "render_reconcile_mr_description"]
