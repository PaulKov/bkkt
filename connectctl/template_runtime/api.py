from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping


PLUGIN_ATTR = "__bkkt_function__"


@dataclass(frozen=True)
class FunctionSpec:
    name: str
    description: str = ""
    deprecated_since: str | None = None
    remove_after: str | None = None
    replacement: str | None = None
    capabilities: tuple[str, ...] = ()
    timeout_ms: int | None = None


@dataclass(frozen=True)
class VariableContext:
    """Read-only placeholder context exposed to repo-local functions."""

    values: Mapping[str, Any] = field(default_factory=dict)
    sources: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "sources", MappingProxyType(dict(self.sources)))

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def source_for(self, key: str) -> str | None:
        return self.sources.get(key)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.values)

    def sources_dict(self) -> dict[str, str]:
        return dict(self.sources)


@dataclass(frozen=True)
class FunctionContext:
    """Execution context for `${fn:...}` functions.

    The context is intentionally read-only. Functions may inspect rendered
    variables and metadata, but they must not mutate render state.
    """

    variables: VariableContext
    repo_root: Path | None = None
    manifest_path: Path | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def from_flat_context(
        cls,
        context: Mapping[str, Any],
        *,
        sources: Mapping[str, str] | None = None,
        repo_root: Path | None = None,
        manifest_path: Path | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "FunctionContext":
        return cls(
            variables=VariableContext(context, sources or {}),
            repo_root=repo_root,
            manifest_path=manifest_path,
            metadata=metadata or {},
        )


def bkkt_function(
    _fn: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str = "",
    deprecated_since: str | None = None,
    remove_after: str | None = None,
    replacement: str | None = None,
    capabilities: tuple[str, ...] = (),
    timeout_ms: int | None = None,
) -> Callable[..., Any]:
    """Mark a Python callable as a BKKT repo-local placeholder function."""

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn_name = (name or fn.__name__).strip()
        setattr(
            fn,
            PLUGIN_ATTR,
            FunctionSpec(
                name=fn_name,
                description=description or (fn.__doc__ or ""),
                deprecated_since=deprecated_since,
                remove_after=remove_after,
                replacement=replacement,
                capabilities=tuple(
                    item.strip() for item in capabilities if item.strip()
                ),
                timeout_ms=timeout_ms,
            ),
        )
        return fn

    if _fn is not None:
        return decorate(_fn)
    return decorate
