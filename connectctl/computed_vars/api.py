from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping


COMPUTED_VAR_ATTR = "__bkkt_computed_var__"


@dataclass(frozen=True)
class ComputedVarSpec:
    name: str
    description: str = ""
    allow_shadow: bool = False
    dependencies: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComputedVariableContext:
    """Read-only placeholder context exposed to computed variables."""

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
class ComputedVarContext:
    """Read-only context exposed to repo-local computed variables."""

    variables: ComputedVariableContext
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
    ) -> "ComputedVarContext":
        return cls(
            variables=ComputedVariableContext(context, sources or {}),
            repo_root=repo_root,
            manifest_path=manifest_path,
            metadata=metadata or {},
        )


def bkkt_computed_var(
    _fn: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str = "",
    allow_shadow: bool = False,
    depends_on: tuple[str, ...] = (),
    capabilities: tuple[str, ...] = (),
) -> Callable[..., Any]:
    """Mark a callable as a BKKT repo-local computed variable."""

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        var_name = (name or fn.__name__).strip()
        setattr(
            fn,
            COMPUTED_VAR_ATTR,
            ComputedVarSpec(
                name=var_name,
                description=description or (fn.__doc__ or ""),
                allow_shadow=allow_shadow,
                dependencies=tuple(item.strip() for item in depends_on if item.strip()),
                capabilities=tuple(
                    item.strip() for item in capabilities if item.strip()
                ),
            ),
        )
        return fn

    if _fn is not None:
        return decorate(_fn)
    return decorate
