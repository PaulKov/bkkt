from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProtobufDescriptor:
    package: str | None
    messages: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "package": self.package,
            "messages": list(self.messages),
        }


@dataclass(frozen=True)
class ProtobufPreflight:
    current: ProtobufDescriptor | None
    candidate: ProtobufDescriptor | None
    warnings: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "current": self.current.to_payload() if self.current else None,
            "candidate": self.candidate.to_payload() if self.candidate else None,
            "warnings": list(self.warnings),
        }


_PACKAGE_RE = re.compile(
    r"^\s*package\s+(?P<package>[A-Za-z_][A-Za-z0-9_.]*)\s*;",
    re.MULTILINE,
)
_MESSAGE_RE = re.compile(
    r"^\s*message\s+(?P<message>[A-Za-z_][A-Za-z0-9_]*)\s*\{",
    re.MULTILINE,
)


def describe_protobuf(schema: str) -> ProtobufDescriptor:
    package_match = _PACKAGE_RE.search(schema)
    messages = tuple(
        dict.fromkeys(match.group("message") for match in _MESSAGE_RE.finditer(schema))
    )
    return ProtobufDescriptor(
        package=package_match.group("package") if package_match else None,
        messages=messages,
    )


def compare_protobuf(
    *,
    current_schema: str | None,
    candidate_schema: str,
) -> ProtobufPreflight:
    current = describe_protobuf(current_schema) if current_schema is not None else None
    candidate = describe_protobuf(candidate_schema)
    warnings: list[str] = []

    if current is not None and current.package != candidate.package:
        warnings.append(
            "PACKAGE_CHANGED risk: Protobuf package changed "
            f"from {current.package or '<none>'} to {candidate.package or '<none>'}. "
            "Some Schema Registry deployments reject this even when generic "
            "compatibility checks are otherwise green."
        )

    if current is not None:
        removed = sorted(set(current.messages) - set(candidate.messages))
        if removed:
            warnings.append(
                "Removed Protobuf messages: " + ", ".join(removed) + ". "
                "Verify consumer impact before registering."
            )

    if not candidate.messages:
        warnings.append(
            "No top-level Protobuf messages were detected in the candidate schema."
        )

    return ProtobufPreflight(
        current=current,
        candidate=candidate,
        warnings=tuple(warnings),
    )
