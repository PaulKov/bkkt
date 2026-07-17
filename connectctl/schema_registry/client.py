from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import requests

from ..exceptions import ConnectCtlError
from ..models import SchemaRegistryConfig


@dataclass(frozen=True)
class SchemaVersion:
    subject: str
    version: str
    schema_id: int | None = None
    schema_type: str = "AVRO"
    schema: str = ""
    references: tuple[dict[str, Any], ...] = ()

    def to_payload(self, *, include_schema: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "subject": self.subject,
            "version": self.version,
            "id": self.schema_id,
            "schema_type": self.schema_type,
            "references": list(self.references),
        }
        if include_schema:
            payload["schema"] = self.schema
        return payload


@dataclass(frozen=True)
class SubjectDescription:
    subject: str
    versions: tuple[int, ...] = ()
    latest: SchemaVersion | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "versions": list(self.versions),
            "latest": self.latest.to_payload() if self.latest else None,
        }


@dataclass(frozen=True)
class CompatibilityCheck:
    subject: str | None
    version: str
    compatible: bool
    messages: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "version": self.version,
            "compatible": self.compatible,
            "messages": list(self.messages),
        }


@dataclass(frozen=True)
class CompatibilityUpdate:
    subject: str | None
    compatibility: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "compatibility": self.compatibility,
        }


@dataclass(frozen=True)
class SchemaDiff:
    subject: str
    from_version: str
    to_version: str
    from_schema_type: str
    to_schema_type: str
    unified_diff: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "from_schema_type": self.from_schema_type,
            "to_schema_type": self.to_schema_type,
            "unified_diff": list(self.unified_diff),
        }


@dataclass(frozen=True)
class SchemaRegistration:
    subject: str
    schema_id: int | None = None
    version: str | None = None
    schema_type: str = "AVRO"

    def to_payload(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "id": self.schema_id,
            "version": self.version,
            "schema_type": self.schema_type,
        }


@dataclass(frozen=True)
class SchemaImpact:
    subject: str
    topic: str | None
    key_or_value: str | None
    suggested_commands: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "topic": self.topic,
            "key_or_value": self.key_or_value,
            "suggested_commands": list(self.suggested_commands),
            "notes": list(self.notes),
        }


Transport = Callable[..., requests.Response]


class SchemaRegistryReadClient:
    """Small Confluent-compatible Schema Registry read facade.

    It is deliberately transport-focused. Output shaping, policy context, and UX
    live in `services.schema_registry` so UI and CLI can reuse one service layer.
    """

    def __init__(
        self,
        cfg: SchemaRegistryConfig,
        *,
        transport: Transport | None = None,
    ) -> None:
        self.cfg = cfg
        self._transport = transport or requests.request

    def list_subjects(
        self, *, prefix: str | None = None, regex: str | None = None, limit: int = 500
    ) -> list[str]:
        subjects = [str(x) for x in self._request("GET", "/subjects")]
        if prefix:
            subjects = [subject for subject in subjects if subject.startswith(prefix)]
        if regex:
            rx = re.compile(regex)
            subjects = [subject for subject in subjects if rx.search(subject)]
        return sorted(subjects)[: int(limit or 500)]

    def list_versions(self, subject: str) -> list[int]:
        return [int(x) for x in self._request("GET", f"/subjects/{subject}/versions")]

    def get_version(self, subject: str, version: str | int = "latest") -> SchemaVersion:
        raw = self._request("GET", f"/subjects/{subject}/versions/{version}")
        return _version_from_raw(
            raw, fallback_subject=subject, fallback_version=version
        )

    def describe_subject(self, subject: str) -> SubjectDescription:
        versions = tuple(self.list_versions(subject))
        latest = self.get_version(subject, "latest") if versions else None
        return SubjectDescription(subject=subject, versions=versions, latest=latest)

    def get_compatibility(self, subject: str | None = None) -> str:
        path = f"/config/{subject}" if subject else "/config"
        raw = self._request("GET", path)
        return str(raw.get("compatibilityLevel") or raw.get("compatibility") or "")

    def set_compatibility(
        self, *, mode: str, subject: str | None = None
    ) -> CompatibilityUpdate:
        path = f"/config/{subject}" if subject else "/config"
        raw = self._request("PUT", path, json={"compatibility": mode})
        return CompatibilityUpdate(
            subject=subject,
            compatibility=str(
                raw.get("compatibilityLevel") or raw.get("compatibility") or mode
            ),
        )

    def check_compatibility(
        self,
        *,
        subject: str,
        schema: str,
        version: str = "latest",
        schema_type: str | None = None,
        references: Sequence[Mapping[str, Any]] = (),
    ) -> CompatibilityCheck:
        body: dict[str, Any] = {"schema": schema}
        if schema_type:
            body["schemaType"] = schema_type
        if references:
            body["references"] = [dict(item) for item in references]
        raw = self._request(
            "POST",
            f"/compatibility/subjects/{subject}/versions/{version}",
            json=body,
        )
        return CompatibilityCheck(
            subject=subject,
            version=str(version),
            compatible=bool(raw.get("is_compatible", raw.get("isCompatible", False))),
            messages=tuple(str(x) for x in raw.get("messages") or []),
        )

    def register_schema(
        self,
        *,
        subject: str,
        schema: str,
        schema_type: str | None = None,
        references: Sequence[Mapping[str, Any]] = (),
    ) -> SchemaRegistration:
        body: dict[str, Any] = {"schema": schema}
        resolved_type = schema_type or "AVRO"
        if schema_type:
            body["schemaType"] = schema_type
        if references:
            body["references"] = [dict(item) for item in references]
        raw = self._request("POST", f"/subjects/{subject}/versions", json=body)
        return SchemaRegistration(
            subject=subject,
            schema_id=_maybe_int(raw.get("id")),
            version=str(raw.get("version")) if raw.get("version") is not None else None,
            schema_type=resolved_type,
        )

    def diff_versions(
        self, *, subject: str, from_version: str | int, to_version: str | int
    ) -> SchemaDiff:
        left = self.get_version(subject, from_version)
        right = self.get_version(subject, to_version)
        diff = tuple(
            difflib.unified_diff(
                left.schema.splitlines(),
                right.schema.splitlines(),
                fromfile=f"{subject}@{left.version}",
                tofile=f"{subject}@{right.version}",
                lineterm="",
            )
        )
        return SchemaDiff(
            subject=subject,
            from_version=str(left.version),
            to_version=str(right.version),
            from_schema_type=left.schema_type,
            to_schema_type=right.schema_type,
            unified_diff=diff,
        )

    def impact(self, subject: str) -> SchemaImpact:
        topic, key_or_value = infer_topic_from_subject(subject)
        commands: list[str] = []
        if topic:
            commands.extend(
                [
                    f"bkkt search --source repo --env prod --topic '{topic}'",
                    f"bkkt lineage '{topic}' --source both --env prod --cluster all --output mermaid",
                ]
            )
        notes = [
            "Schema Registry subjects are conventionally '<topic>-key' or '<topic>-value'.",
            "Use search and lineage to verify actual connector and table impact.",
        ]
        return SchemaImpact(
            subject=subject,
            topic=topic,
            key_or_value=key_or_value,
            suggested_commands=tuple(commands),
            notes=tuple(notes),
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        errors: list[str] = []
        for base_url in self.cfg.urls:
            url = f"{str(base_url).rstrip('/')}{path}"
            try:
                resp = self._transport(
                    method,
                    url,
                    timeout=self.cfg.timeout_seconds,
                    auth=_auth_tuple(self.cfg),
                    **kwargs,
                )
                if resp.status_code == 404:
                    errors.append(f"{base_url}: 404 {path}")
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001 - normalized user-facing matrix
                errors.append(f"{base_url}: {type(exc).__name__}: {exc}")
        raise ConnectCtlError(
            "Schema Registry request failed on all configured endpoints: "
            + "; ".join(errors)
        )


def infer_topic_from_subject(subject: str) -> tuple[str | None, str | None]:
    for suffix, kind in (("-key", "key"), ("-value", "value")):
        if subject.endswith(suffix):
            return subject[: -len(suffix)], kind
    return None, None


def _auth_tuple(cfg: SchemaRegistryConfig) -> tuple[str, str] | None:
    if cfg.username is None or cfg.password is None:
        return None
    return (cfg.username, cfg.password)


def _version_from_raw(
    raw: Mapping[str, Any], *, fallback_subject: str, fallback_version: str | int
) -> SchemaVersion:
    return SchemaVersion(
        subject=str(raw.get("subject") or fallback_subject),
        version=str(raw.get("version") or fallback_version),
        schema_id=_maybe_int(raw.get("id")),
        schema_type=str(raw.get("schemaType") or raw.get("schema_type") or "AVRO"),
        schema=str(raw.get("schema") or ""),
        references=tuple(dict(x) for x in raw.get("references") or []),
    )


def _maybe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
