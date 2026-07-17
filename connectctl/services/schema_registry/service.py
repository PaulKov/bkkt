from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from ...app.context import CliContext
from ...exceptions import ConfigError, ConnectCtlError
from ...logging_utils import get_logger
from ...models import Environment, SchemaRegistryConfig
from ...output import (
    is_machine_output,
    resolve_output_format,
    write_payload,
    write_text,
)
from ...schema_registry import SchemaRegistryReadClient
from ..admin_endpoints.resolver import EffectiveAdminEndpointResolver
from .presentation import (
    SchemaScope,
    check_text,
    compat_set_text,
    compat_text,
    diff_text,
    impact_text,
    plan_text,
    register_text,
    subject_describe_text,
    subjects_text,
    version_text,
    versions_text,
)
from .protobuf_preflight import compare_protobuf

SchemaRegistryFactory = Callable[[SchemaRegistryConfig], Any]
COMPATIBILITY_MODES = (
    "BACKWARD",
    "BACKWARD_TRANSITIVE",
    "FORWARD",
    "FORWARD_TRANSITIVE",
    "FULL",
    "FULL_TRANSITIVE",
    "NONE",
)


class SchemaRegistryService:
    """Read-only Schema Registry governance service.

    This service keeps the CLI/UI contract independent from the concrete REST
    client. Tests can inject a fake registry while production uses the
    Confluent-compatible REST facade.
    """

    def __init__(
        self,
        *,
        ctx: CliContext,
        logger=None,
        client_factory: SchemaRegistryFactory | None = None,
    ) -> None:
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)
        self.client_factory = client_factory or SchemaRegistryReadClient

    def run_subjects_list(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        client = self.client_factory(scope.schema_registry)
        subjects = client.list_subjects(
            prefix=getattr(args, "prefix", None),
            regex=getattr(args, "regexp", None),
            limit=int(getattr(args, "limit", 500) or 500),
        )
        payload = {
            **scope.payload(),
            "kind": "schema_subjects_list",
            "subject_count": len(subjects),
            "subjects": subjects,
        }
        return self._write(args, payload=payload, text=subjects_text(scope, subjects))

    def run_subjects_versions(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        subject = _required(args, "subject")
        versions = self.client_factory(scope.schema_registry).list_versions(subject)
        payload = {
            **scope.payload(),
            "kind": "schema_subject_versions",
            "subject": subject,
            "versions": versions,
        }
        return self._write(
            args,
            payload=payload,
            text=versions_text(scope, subject=subject, versions=versions),
        )

    def run_subjects_describe(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        subject = _required(args, "subject")
        version = str(getattr(args, "version", "") or "").strip()
        client = self.client_factory(scope.schema_registry)
        if version:
            desc = client.get_version(subject, version)
            payload = {
                **scope.payload(),
                "kind": "schema_subject_version",
                "schema": desc.to_payload(include_schema=True),
            }
            text = version_text(scope, desc)
        else:
            desc = client.describe_subject(subject)
            payload = {
                **scope.payload(),
                "kind": "schema_subject_describe",
                "subject": desc.to_payload(),
            }
            text = subject_describe_text(scope, desc)
        return self._write(args, payload=payload, text=text)

    def run_subjects_diff(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        subject = _required(args, "subject")
        diff = self.client_factory(scope.schema_registry).diff_versions(
            subject=subject,
            from_version=str(getattr(args, "from_version")),
            to_version=str(getattr(args, "to_version")),
        )
        return self._write(
            args,
            payload={
                **scope.payload(),
                "kind": "schema_subject_diff",
                "diff": diff.to_payload(),
            },
            text=diff_text(scope, diff),
        )

    def run_compatibility_get(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        subject = getattr(args, "subject", None)
        level = self.client_factory(scope.schema_registry).get_compatibility(subject)
        payload = {
            **scope.payload(),
            "kind": "schema_compatibility",
            "subject": subject,
            "compatibility": level,
        }
        return self._write(
            args, payload=payload, text=compat_text(scope, subject, level)
        )

    def run_compatibility_check(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        subject = _required(args, "subject")
        schema_input = _read_schema_input(args)
        check = self.client_factory(scope.schema_registry).check_compatibility(
            subject=subject,
            version=str(getattr(args, "version", "latest") or "latest"),
            schema=schema_input["schema"],
            schema_type=getattr(args, "schema_type", None),
        )
        return self._write(
            args,
            payload={
                **scope.payload(),
                "kind": "schema_compatibility_check",
                "result": check.to_payload(),
            },
            text=check_text(scope, check),
        )

    def run_compatibility_set(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        subject = getattr(args, "subject", None)
        desired = _compatibility_mode(args)
        dry_run = bool(getattr(args, "dry_run", False))
        yes = bool(getattr(args, "yes", False))
        client = self.client_factory(scope.schema_registry)
        current = client.get_compatibility(subject)
        plan = {
            **scope.payload(),
            "kind": "schema_compatibility_set_plan",
            "dry_run": dry_run,
            "applied": False,
            "subject": subject,
            "current_compatibility": current,
            "desired_compatibility": desired,
            "requires_confirmation": not dry_run,
            "actions": [
                {
                    "action": "set_compatibility",
                    "target": subject or "<global>",
                    "from": current,
                    "to": desired,
                }
            ],
        }
        if dry_run:
            return self._write(args, payload=plan, text=compat_set_text(scope, plan))
        if not yes:
            raise ConfigError(
                "Refusing to change Schema Registry compatibility without --yes. "
                "Run with --dry-run first, then repeat with --yes after reviewing the plan."
            )
        result = client.set_compatibility(subject=subject, mode=desired)
        payload = {
            **plan,
            "kind": "schema_compatibility_set",
            "applied": True,
            "result": result.to_payload(),
        }
        return self._write(args, payload=payload, text=compat_set_text(scope, payload))

    def run_register(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        dry_run = bool(getattr(args, "dry_run", False))
        yes = bool(getattr(args, "yes", False))
        plan = self._build_evolution_plan(args, scope=scope)
        payload = {
            **plan,
            "kind": "schema_register_plan" if dry_run else "schema_register",
            "dry_run": dry_run,
            "applied": False,
            "requires_confirmation": not dry_run,
        }
        if dry_run:
            return self._write(
                args, payload=payload, text=register_text(scope, payload)
            )
        if not yes:
            raise ConfigError(
                "Refusing to register a Schema Registry version without --yes. "
                "Run with --dry-run or `bkkt schema plan` first, then repeat with --yes."
            )
        client = self.client_factory(scope.schema_registry)
        schema_input = _read_schema_input(args)
        result = client.register_schema(
            subject=_required(args, "subject"),
            schema=schema_input["schema"],
            schema_type=getattr(args, "schema_type", None),
        )
        payload = {
            **payload,
            "applied": True,
            "result": result.to_payload(),
        }
        return self._write(args, payload=payload, text=register_text(scope, payload))

    def run_plan(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        payload = self._build_evolution_plan(args, scope=scope)
        return self._write(args, payload=payload, text=plan_text(scope, payload))

    def run_impact(self, args: argparse.Namespace) -> int:
        scope = self._scope(args)
        subject = _required(args, "subject")
        impact = self.client_factory(scope.schema_registry).impact(subject)
        return self._write(
            args,
            payload={
                **scope.payload(),
                "kind": "schema_impact",
                "impact": impact.to_payload(),
            },
            text=impact_text(scope, impact),
        )

    def _build_evolution_plan(
        self, args: argparse.Namespace, *, scope: SchemaScope
    ) -> dict[str, Any]:
        subject = _required(args, "subject")
        schema_input = _read_schema_input(args)
        schema_type = str(getattr(args, "schema_type", None) or "AVRO").upper()
        version = str(getattr(args, "version", "latest") or "latest")
        client = self.client_factory(scope.schema_registry)
        current_latest = None
        latest_error = None
        try:
            current_latest = client.get_version(subject, "latest")
        except ConnectCtlError as exc:
            latest_error = str(exc)
        check = client.check_compatibility(
            subject=subject,
            version=version,
            schema=schema_input["schema"],
            schema_type=schema_type,
        )
        impact = client.impact(subject)
        protobuf = None
        if schema_type == "PROTOBUF":
            protobuf = compare_protobuf(
                current_schema=(
                    current_latest.schema
                    if current_latest is not None
                    and str(current_latest.schema_type).upper() == "PROTOBUF"
                    else None
                ),
                candidate_schema=schema_input["schema"],
            )
        warnings = list(protobuf.warnings if protobuf else ())
        if not check.compatible:
            warnings.append(
                "Compatibility check is not green; registration should not proceed "
                "without an explicit migration decision."
            )
        return {
            **scope.payload(),
            "kind": "schema_evolution_plan",
            "subject": subject,
            "version": version,
            "schema_file": schema_input["path"],
            "candidate": {
                "schema_type": schema_type,
                "bytes": schema_input["bytes"],
            },
            "current_latest": (
                current_latest.to_payload(include_schema=False)
                if current_latest is not None
                else None
            ),
            "current_latest_error": latest_error,
            "compatibility": check.to_payload(),
            "impact": impact.to_payload(),
            "protobuf_preflight": protobuf.to_payload() if protobuf else None,
            "warnings": warnings,
            "safe_to_register": check.compatible and not warnings,
            "next_commands": [
                f"bkkt schema compatibility check --env {scope.env.value} "
                f"--cluster {scope.cluster.name} {subject} "
                f"--schema-file {schema_input['path']} --schema-type {schema_type}",
                f"bkkt schema register --env {scope.env.value} "
                f"--cluster {scope.cluster.name} {subject} "
                f"--schema-file {schema_input['path']} --schema-type {schema_type} --dry-run",
            ],
        }

    def _scope(self, args: argparse.Namespace) -> SchemaScope:
        env = Environment.from_str(str(getattr(args, "env")).strip().lower())
        cluster = self.ctx.resolve_cluster(env, getattr(args, "cluster", None))
        endpoint = EffectiveAdminEndpointResolver(self.ctx).resolve_schema_registry(
            env=env,
            cluster=cluster,
            override_url=getattr(args, "url", None),
            timeout_seconds=getattr(args, "timeout_seconds", None),
        )
        return SchemaScope(
            env=env,
            cluster=cluster,
            schema_registry=endpoint.config,
            schema_registry_source=endpoint.source_label,
        )

    def _write(
        self, args: argparse.Namespace, *, payload: dict[str, Any], text: str
    ) -> int:
        fmt = resolve_output_format(args)
        if is_machine_output(fmt):
            write_payload(payload, fmt=fmt)
        else:
            write_text(text)
        return 0


def _required(args: argparse.Namespace, name: str) -> str:
    value = str(getattr(args, name, "") or "").strip()
    if not value:
        raise ConfigError(f"{name} is required")
    return value


def _read_schema_input(args: argparse.Namespace) -> dict[str, Any]:
    schema_file = Path(str(getattr(args, "schema_file"))).resolve()
    if not schema_file.exists():
        raise ConfigError(f"Schema file not found: {schema_file}")
    schema = schema_file.read_text(encoding="utf-8")
    return {
        "path": str(schema_file),
        "schema": schema,
        "bytes": len(schema.encode("utf-8")),
    }


def _compatibility_mode(args: argparse.Namespace) -> str:
    mode = str(getattr(args, "mode", "") or "").strip().upper()
    if mode not in COMPATIBILITY_MODES:
        allowed = ", ".join(COMPATIBILITY_MODES)
        raise ConfigError(
            f"Unsupported compatibility mode={mode!r}. Allowed: {allowed}"
        )
    return mode
