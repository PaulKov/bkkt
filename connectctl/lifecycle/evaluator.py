from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from ..exceptions import RenderError
from .models import ConnectorLifecycle


@dataclass(frozen=True)
class LifecycleEvaluation:
    lifecycle: ConnectorLifecycle
    connectctl_meta: Dict[str, Any]
    connectctl_sources: Dict[str, str]


class LifecycleEvaluator:
    """Build effective lifecycle state from raw connectctl.lifecycle layer blocks."""

    def __init__(self) -> None:
        self._seen = False
        self._disabled = False
        self._reason: Optional[str] = None
        self._ticket: Optional[str] = None
        self._until: Optional[str] = None
        self._disabled_sources: list[str] = []
        self._disabled_source_key: Optional[str] = None
        self._reason_source: Optional[str] = None
        self._ticket_source: Optional[str] = None
        self._until_source: Optional[str] = None

    def apply(self, raw: Any, *, rel_source: str) -> None:
        if raw is None:
            return
        if not isinstance(raw, Mapping):
            raise RenderError(f"connectctl.lifecycle must be an object in {rel_source}")

        self._seen = True
        lifecycle = dict(raw)
        self._reject_unknown_keys(lifecycle, rel_source=rel_source)

        disabled = lifecycle.get("disabled")
        if disabled is not None and not isinstance(disabled, bool):
            raise RenderError(
                f"connectctl.lifecycle.disabled must be boolean in {rel_source}"
            )

        if disabled is True:
            self._disabled = True
            self._disabled_sources.append(rel_source)
            if self._disabled_source_key is None:
                self._disabled_source_key = f"connectctl:{rel_source}"

        if self._disabled:
            self._apply_string_field(
                lifecycle.get("reason"),
                field_name="reason",
                rel_source=rel_source,
            )
            self._apply_string_field(
                lifecycle.get("ticket"),
                field_name="ticket",
                rel_source=rel_source,
            )
            self._apply_string_field(
                lifecycle.get("until"),
                field_name="until",
                rel_source=rel_source,
            )

    def build(self) -> LifecycleEvaluation:
        lifecycle = ConnectorLifecycle(
            disabled=self._disabled,
            reason=self._reason,
            ticket=self._ticket,
            until=self._until,
            disabled_sources=tuple(self._disabled_sources),
        )
        if lifecycle.disabled and not lifecycle.reason:
            layers = ", ".join(lifecycle.disabled_sources) or "<unknown>"
            raise RenderError(
                "connectctl.lifecycle.reason is required when effective lifecycle is disabled "
                f"(disabled by: {layers})"
            )

        meta: Dict[str, Any] = {}
        sources: Dict[str, str] = {}
        if self._seen:
            meta["lifecycle"] = lifecycle.to_meta()
            if self._disabled_source_key is not None:
                sources["lifecycle.disabled"] = self._disabled_source_key
            if lifecycle.reason and self._reason_source is not None:
                sources["lifecycle.reason"] = self._reason_source
            if lifecycle.ticket and self._ticket_source is not None:
                sources["lifecycle.ticket"] = self._ticket_source
            if lifecycle.until and self._until_source is not None:
                sources["lifecycle.until"] = self._until_source

        return LifecycleEvaluation(
            lifecycle=lifecycle,
            connectctl_meta=meta,
            connectctl_sources=sources,
        )

    def _apply_string_field(
        self, raw: Any, *, field_name: str, rel_source: str
    ) -> None:
        if raw is None:
            return
        if not isinstance(raw, str):
            raise RenderError(
                f"connectctl.lifecycle.{field_name} must be a string in {rel_source}"
            )
        value = raw.strip()
        if not value:
            return
        setattr(self, f"_{field_name}", value)
        setattr(self, f"_{field_name}_source", f"connectctl:{rel_source}")

    def _reject_unknown_keys(
        self, lifecycle: Mapping[str, Any], *, rel_source: str
    ) -> None:
        allowed = {"disabled", "reason", "ticket", "until"}
        extra = sorted(set(lifecycle.keys()) - allowed)
        if extra:
            raise RenderError(
                f"Unsupported connectctl.lifecycle key(s) in {rel_source}: {', '.join(extra)}"
            )
