from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .utils import (
    cluster_group_from_payload,
    selector_tokens_from_extra,
    string_or_none,
)


@dataclass(frozen=True)
class FailureRemediation:
    category: str
    summary: str
    actions: tuple[str, ...] = ()
    commands: tuple[str, ...] = ()
    references: tuple[str, ...] = ()

    def as_payload(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "summary": self.summary,
            "actions": list(self.actions),
            "commands": list(self.commands),
            "references": list(self.references),
        }


@dataclass(frozen=True)
class FailureAnalysisContext:
    command: str
    env: str
    stage: str
    error: BaseException
    manifest_meta: Mapping[str, Any]
    routing_payload: Mapping[str, Any]
    pruned_config_keys: tuple[str, ...]
    extra: Mapping[str, Any]
    path: str | None
    name: str | None
    cluster_group: str | None
    error_type: str
    message: str
    normalized_message: str
    input_src: str | None
    selector_tokens: tuple[str, ...]
    pruned_hint: str

    @classmethod
    def from_parts(
        cls,
        *,
        command: str,
        env: str,
        stage: str,
        error: BaseException,
        manifest_meta: Mapping[str, Any],
        routing_payload: Mapping[str, Any],
        pruned_config_keys: Sequence[str],
        extra: Mapping[str, Any],
    ) -> "FailureAnalysisContext":
        manifest_meta_dict = dict(manifest_meta)
        routing_payload_dict = dict(routing_payload)
        extra_dict = dict(extra)
        path = string_or_none(
            manifest_meta_dict.get("path") or manifest_meta_dict.get("requested_path")
        )
        name = string_or_none(manifest_meta_dict.get("name") or extra_dict.get("name"))
        cluster_group = cluster_group_from_payload(
            manifest_meta_dict, routing_payload_dict
        ) or string_or_none(extra_dict.get("cluster_group"))
        message = str(error).strip()
        pruned_keys = tuple(str(key) for key in pruned_config_keys)
        pruned_hint = (
            " Target cluster prune removed "
            f"{len(pruned_keys)} key(s); review routing.json if the failure looks "
            "cluster-specific."
            if pruned_keys
            else ""
        )
        return cls(
            command=command,
            env=env,
            stage=stage,
            error=error,
            manifest_meta=manifest_meta_dict,
            routing_payload=routing_payload_dict,
            pruned_config_keys=pruned_keys,
            extra=extra_dict,
            path=path,
            name=name,
            cluster_group=cluster_group,
            error_type=error.__class__.__name__,
            message=message,
            normalized_message=message.casefold(),
            input_src=string_or_none(extra_dict.get("input_src")),
            selector_tokens=selector_tokens_from_extra(extra_dict),
            pruned_hint=pruned_hint,
        )
