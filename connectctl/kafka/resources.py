from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from ..exceptions import ConfigError


@dataclass(frozen=True)
class KafkaTopicManifest:
    name: str
    partitions: int
    replication_factor: int
    configs: dict[str, str] = field(default_factory=dict)
    owner: str | None = None
    description: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "partitions": self.partitions,
            "replication_factor": self.replication_factor,
            "configs": dict(sorted(self.configs.items())),
        }
        if self.owner:
            payload["owner"] = self.owner
        if self.description:
            payload["description"] = self.description
        return payload


def load_topic_manifests(path: Path) -> list[KafkaTopicManifest]:
    """Load declarative Kafka topic manifests from JSON/YAML file or directory."""

    target = path.resolve()
    if target.is_dir():
        files = [
            item
            for item in sorted(target.rglob("*"))
            if item.suffix.lower() in {".json", ".yaml", ".yml"}
        ]
        if not files:
            raise ConfigError(f"No Kafka topic manifests found under: {target}")
        manifests: list[KafkaTopicManifest] = []
        for item in files:
            manifests.extend(load_topic_manifests(item))
        return manifests
    if not target.exists():
        raise ConfigError(f"Kafka topic manifest not found: {target}")
    raw = _read_structured_file(target)
    return [_manifest_from_obj(item, source=target) for item in _topic_items(raw)]


def _read_structured_file(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def _topic_items(raw: Any) -> list[Mapping[str, Any]]:
    if isinstance(raw, Mapping):
        if isinstance(raw.get("topics"), list):
            return [item for item in raw["topics"] if isinstance(item, Mapping)]
        if str(raw.get("kind", "")).lower() in {"kafka_topic", "kafka-topic"}:
            return [raw]
        if "name" in raw:
            return [raw]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, Mapping)]
    raise ConfigError("Kafka topic manifest must contain a topic object or topics list")


def _manifest_from_obj(obj: Mapping[str, Any], *, source: Path) -> KafkaTopicManifest:
    name = str(obj.get("name", "") or "").strip()
    if not name:
        raise ConfigError(f"{source}: topic name is required")
    return KafkaTopicManifest(
        name=name,
        partitions=_positive_int(obj.get("partitions"), "partitions", source),
        replication_factor=_positive_int(
            obj.get("replication_factor", obj.get("replicationFactor")),
            "replication_factor",
            source,
        ),
        configs=_string_map(obj.get("configs") or {}, source=source),
        owner=_optional_str(obj.get("owner")),
        description=_optional_str(obj.get("description")),
    )


def _positive_int(value: Any, field_name: str, source: Path) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{source}: {field_name} must be a positive integer") from exc
    if out <= 0:
        raise ConfigError(f"{source}: {field_name} must be a positive integer")
    return out


def _string_map(raw: Any, *, source: Path) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{source}: configs must be an object")
    return {str(key): str(value) for key, value in raw.items()}


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = ["KafkaTopicManifest", "load_topic_manifests"]
