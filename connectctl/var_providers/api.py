from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any


VAR_PROVIDER_ATTR = "__bkkt_var_provider__"


@dataclass(frozen=True)
class VarProviderSpec:
    name: str
    description: str = ""
    provides: tuple[str, ...] = ()
    allow_shadow: bool = False
    capabilities: tuple[str, ...] = ()
    timeout_ms: int | None = None


@dataclass(frozen=True)
class ProviderVariableContext:
    """Read-only variables visible to repo-local variable providers."""

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
class VarProviderContext:
    """Execution context for repo-local variable providers."""

    variables: ProviderVariableContext
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
    ) -> "VarProviderContext":
        return cls(
            variables=ProviderVariableContext(context, sources or {}),
            repo_root=repo_root,
            manifest_path=manifest_path,
            metadata=metadata or {},
        )


def bkkt_var_provider(
    _fn: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str = "",
    provides: tuple[str, ...] = (),
    allow_shadow: bool = False,
    capabilities: tuple[str, ...] = (),
    timeout_ms: int | None = None,
) -> Callable[..., Any]:
    """Mark a callable as a BKKT repo-local variable provider."""

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        provider_name = (name or fn.__name__).strip()
        setattr(
            fn,
            VAR_PROVIDER_ATTR,
            VarProviderSpec(
                name=provider_name,
                description=description or (fn.__doc__ or ""),
                provides=tuple(item.strip() for item in provides if item.strip()),
                allow_shadow=allow_shadow,
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
