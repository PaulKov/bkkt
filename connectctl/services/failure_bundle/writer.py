from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from ...ports import FileSystem
from .command_catalog import FailureCommandCatalog
from .inline import attach_inline_remediation
from .models import FailureAnalysisContext
from .payload_builder import FailureBundlePayloadBuilder
from .planner import FailureRemediationPlanner
from .readme_renderer import FailureBundleReadmeRenderer
from .utils import slug


@dataclass(frozen=True)
class FailureBundleWriter:
    command: str
    repo_root: Path
    fs: FileSystem
    root_dir: Path
    planner: FailureRemediationPlanner = field(
        default_factory=FailureRemediationPlanner
    )
    payload_builder: FailureBundlePayloadBuilder = field(
        default_factory=FailureBundlePayloadBuilder
    )
    readme_renderer: FailureBundleReadmeRenderer = field(
        default_factory=FailureBundleReadmeRenderer
    )

    @classmethod
    def from_args(
        cls,
        *,
        command: str,
        repo_root: Path,
        fs: FileSystem,
        args: object,
    ) -> "FailureBundleWriter":
        root_raw = getattr(args, "failure_bundle_dir", None)
        root_dir = (
            Path(str(root_raw)).resolve()
            if root_raw
            else (repo_root / "artifacts" / "failure-bundles" / command).resolve()
        )
        return cls(command=command, repo_root=repo_root, fs=fs, root_dir=root_dir)

    def write(
        self,
        *,
        env: str,
        stage: str,
        error: BaseException,
        manifest_meta: Optional[Mapping[str, Any]] = None,
        prepared_manifest: Optional[Mapping[str, Any]] = None,
        routing_payload: Optional[Mapping[str, Any]] = None,
        routing_debug: Optional[Mapping[str, Any]] = None,
        pruned_config_keys: Sequence[str] = (),
        extra: Optional[Mapping[str, Any]] = None,
    ) -> Path:
        created_at = datetime.now(timezone.utc)
        created_at_iso = created_at.isoformat().replace("+00:00", "Z")
        context = FailureAnalysisContext.from_parts(
            command=self.command,
            env=env,
            stage=stage,
            error=error,
            manifest_meta=dict(manifest_meta or {}),
            routing_payload=dict(routing_payload or {}),
            pruned_config_keys=pruned_config_keys,
            extra=dict(extra or {}),
        )
        remediation = self.planner.plan(
            context, FailureCommandCatalog.from_context(context)
        )
        attach_inline_remediation(error, remediation=remediation)

        bundle_dir = self._make_bundle_dir(context=context, created_at=created_at)
        self.fs.mkdirs(bundle_dir, exist_ok=True)

        bundle_payload = self.payload_builder.build(
            command=self.command,
            context=context,
            created_at_iso=created_at_iso,
            remediation=remediation,
            prepared_manifest=prepared_manifest,
            routing_debug=routing_debug,
        )
        self._write_json(bundle_dir / "bundle.json", bundle_payload)

        if prepared_manifest is not None:
            self._write_json(
                bundle_dir / "prepared_manifest.json", dict(prepared_manifest)
            )

        if routing_payload is not None or routing_debug is not None:
            self._write_json(
                bundle_dir / "routing.json",
                {
                    "routing": dict(routing_payload or {}),
                    "debug": dict(routing_debug or {}),
                },
            )

        self.fs.write_text(
            bundle_dir / "README.md",
            self.readme_renderer.render(
                command=self.command,
                env=env,
                stage=stage,
                created_at_iso=created_at_iso,
                error=error,
                remediation=remediation,
            ),
            encoding="utf-8",
        )
        attach_inline_remediation(error, remediation=remediation, bundle_dir=bundle_dir)
        return bundle_dir

    def _make_bundle_dir(
        self,
        *,
        context: FailureAnalysisContext,
        created_at: datetime,
    ) -> Path:
        connector_label = (
            str(context.manifest_meta.get("name"))
            or str(context.manifest_meta.get("path"))
            or context.stage
        )
        return self.root_dir / (
            f"{created_at.strftime('%Y%m%dT%H%M%S.%fZ')}-{slug(connector_label)}"
        )

    def _write_json(self, path: Path, payload: Mapping[str, Any]) -> None:
        self.fs.write_text(
            path,
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
